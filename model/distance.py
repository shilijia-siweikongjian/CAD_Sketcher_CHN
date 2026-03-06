import logging
import math

from bpy.types import PropertyGroup
from bpy.props import BoolProperty, FloatProperty, EnumProperty
from bpy.utils import register_classes_factory
from mathutils import Vector, Matrix
from mathutils.geometry import distance_point_to_plane, intersect_point_line

from ..solver import Solver
from ..utilities import preferences
from ..global_data import WpReq
from ..utilities.view import location_3d_to_region_2d
from ..utilities.math import range_2pi
from .base_constraint import DimensionalConstraint
from .utilities import slvs_entity_pointer
from .categories import POINT, LINE, POINT2D, CURVE
from ..utilities.solver import update_system_cb
from ..utilities.bpy import setprop, bpyEnum

from .workplane import SlvsWorkplane
from .point_3d import SlvsPoint3D
from .line_3d import SlvsLine3D
from .point_2d import SlvsPoint2D
from .line_2d import SlvsLine2D
from .arc import SlvsArc
from .circle import SlvsCircle

logger = logging.getLogger(__name__)


def get_side_of_line(line_start, line_end, point):
    """计算点相对于线段的方向（用于符号距离）"""
    line_end = line_end - line_start
    point = point - line_start
    return -(
        (line_end.x - line_start.x) * (point.y - line_start.y)
        - (line_end.y - line_start.y) * (point.x - line_start.x)
    )


def _get_aligned_distance(p_1, p_2, alignment):
    """根据对齐方式计算两点间的距离"""
    if alignment == "HORIZONTAL":
        return abs(p_2.co.x - p_1.co.x)
    if alignment == "VERTICAL":
        return abs(p_2.co.y - p_1.co.y)
    return (p_2.co - p_1.co).length


align_items = [
    ("NONE", "无", "", 0),
    ("HORIZONTAL", "水平", "", 1),
    ("VERTICAL", "垂直", "", 2),
]

def _get_value(self):
    """获取显示值（考虑参考尺寸和对齐）"""
    if self.is_reference:
        val = self.init_props(align=self.align)["value"]
        return self.to_displayed_value(val)
    if not self.is_property_set("value_store"):
        self.assign_init_props()
    return self.to_displayed_value(self.value_store)


class SlvsDistance(DimensionalConstraint, PropertyGroup):
    """设置一个点与另一个实体（点/线/工作平面）之间的距离。"""

    def _set_value_force(self, value):
        """强制设置距离值（取绝对值）"""
        DimensionalConstraint._set_value_force(self, abs(value))

    def _set_align(self, value: int):
        """根据对齐方式设置距离值"""
        alignment = bpyEnum(align_items, value).identifier
        distance = _get_aligned_distance(self.entity1, self.entity2, alignment)
        self.align_store = value
        self.value_store = distance

    def _get_align(self) -> int:
        """获取对齐方式存储值"""
        if not self.is_property_set("align_store"):
            return 0
        return self.align_store

    label = "距离"
    value_store: FloatProperty(
        name="值存储",
        subtype="DISTANCE",
        unit="LENGTH",
        precision=6,
    )
    align_store: EnumProperty(
        name="对齐存储",
        items=align_items,
    )
    value: FloatProperty(
        name=label,
        subtype="DISTANCE",
        unit="LENGTH",
        precision=6,
        update=update_system_cb,
        get=_get_value,
        set=DimensionalConstraint._set_value,
    )
    flip: BoolProperty(name="翻转", update=update_system_cb)
    align: EnumProperty(
        name="对齐",
        items=align_items,
        update=update_system_cb,
        get=_get_align,
        set=_set_align,
    )
    draw_offset: FloatProperty(name="绘制偏移", default=0.3)
    draw_outset: FloatProperty(name="绘制外扩", default=0.0)
    type = "DISTANCE"
    signature = ((*POINT, *LINE, SlvsCircle, SlvsArc), (*POINT, *LINE, SlvsWorkplane))
    props = ("value",)

    @classmethod
    def get_types(cls, index, entities):
        """获取约束类型签名"""
        e = entities[1] if index == 0 else entities[0]

        if e:
            if index == 1 and e.is_line():
                # 允许约束单条直线
                return None
            if e.is_3d():
                return ((SlvsPoint3D,), (SlvsPoint3D, SlvsLine3D, SlvsWorkplane))[index]
            return (POINT2D, (*POINT2D, SlvsLine2D))[index]
        return cls.signature[index]

    def needs_wp(self):
        """是否需要工作平面"""
        if isinstance(self.entity2, SlvsWorkplane):
            return WpReq.FREE
        return WpReq.OPTIONAL

    def use_flipping(self):
        """是否可以使用翻转（仅点与线/工作平面之间）"""
        if self.entity1.is_curve():
            return False
        return type(self.entity2) in (*LINE, SlvsWorkplane)

    def use_align(self):
        """是否可以对齐（两点之间且非曲线）"""
        if type(self.entity2) in (*LINE, SlvsWorkplane):
            return False
        if self.entity1.is_curve():
            return False
        return True

    def is_align(self):
        """返回是否已启用对齐"""
        return self.use_align() and self.align != "NONE"

    def get_value(self):
        """获取当前距离值（考虑翻转）"""
        value = self.value
        if self.use_flipping() and self.flip:
            return value * -1
        return value

    def create_slvs_data(self, solvesys, group=Solver.group_fixed):
        """在求解器中创建约束数据"""
        if self.entity1 == self.entity2:
            raise AttributeError("不能创建约束于同一个实体自身")
        # TODO: 不允许点与线之间的距离（如果点在线上的情况）

        e1, e2 = self.entity1, self.entity2
        if e1.is_line():
            e1, e2 = e1.p1, e1.p2

        func = None
        set_wp = False
        wp = self.get_workplane()
        alignment = self.align
        align = self.is_align()
        handles = []

        value = self.get_value()

        # 曲线 -> 线/点
        if type(e1) in CURVE:
            # TODO: 使水平和垂直对齐生效
            if type(e2) in LINE:
                return solvesys.distance(
                    group, e1.ct.py_data, e2.py_data, value + e1.radius, wp
                )
            else:
                assert isinstance(e2, SlvsPoint2D)
                return solvesys.distance(
                    group, e1.ct.py_data, e2.py_data, value + e1.radius, wp
                )

        elif type(e2) in LINE:
            func = solvesys.distance
            set_wp = True
        elif isinstance(e2, SlvsWorkplane):
            func = solvesys.distance
        elif type(e2) in POINT:
            if align and all([e.is_2d() for e in (e1, e2)]):

                # 获取中间点
                p1, p2 = e1.co, e2.co
                coords = (p2.x, p1.y)

                p = solvesys.add_point_2d(group, *coords, wp)

                handles.append(
                    solvesys.horizontal(group, p, wp, entityB=e2.py_data)
                )
                handles.append(
                    solvesys.vertical(group, p, wp, entityB=e1.py_data)
                )

                base_point = e1 if alignment == "VERTICAL" else e2
                handles.append(
                    solvesys.distance(
                        group, p, base_point.py_data, value, wp
                    )
                )
                return handles
            else:
                func = solvesys.distance
            set_wp = True

        args = []
        if set_wp:
            args.append(self.get_workplane())

        return func(group, e1.py_data, e2.py_data, value, *args)

    def matrix_basis(self):
        """计算约束显示的基础矩阵"""
        if self.sketch_i == -1 or not self.entity1.is_2d():
            # TODO: 支持3D中的距离显示
            return Matrix()

        sketch = self.sketch
        x_axis = Vector((1, 0))
        alignment = self.align
        align = self.is_align()
        angle = 0

        e1, e2 = self.entity1, self.entity2
        #   e1       e2
        #   ----------------
        #   线       [无]
        #   点       点
        #   点       线
        #   弧       点
        #   弧       线
        #   圆       点
        #   圆       线

        # 设置 p1 和 p2
        if e1.is_curve():
            # 重新视为点->点并继续
            centerpoint = e1.ct.co
            if e2.is_line():
                p2, _ = intersect_point_line(centerpoint, e2.p1.co, e2.p2.co)
            else:
                assert isinstance(e2, SlvsPoint2D)
                p2 = e2.co
            if (p2 - centerpoint).length > 0:
                vec = (p2 - centerpoint) / (p2 - centerpoint).length
                p1 = centerpoint + (e1.radius * Vector(vec))
            else:
                # 曲线->线且曲线的中心点与线重合的情况
                # 通过将 p1 重新指定为线的端点，避免 p1=p2 错误，结果（正确地）是无效约束
                p1 = e2.p1.co
        elif e1.is_line():
            # 重新视为点->点并继续
            e1, e2 = e1.p1, e1.p2
            p1, p2 = e1.co, e2.co
        else:
            assert isinstance(e1, SlvsPoint2D)
            p1 = e1.co

        if type(e2) in POINT2D:
            # 包括“线段长度”（现在为点->点）
            # 以及曲线->点
            p2 = e2.co
            if not align:
                v_rotation = p2 - p1
            else:
                v_rotation = (
                    Vector((1.0, 0.0))
                    if alignment == "HORIZONTAL"
                    else Vector((0.0, 1.0))
                )

            if v_rotation.length != 0:
                angle = v_rotation.angle_signed(x_axis)
                
            mat_rot = Matrix.Rotation(angle, 2, "Z")
            v_translation = (p2 + p1) / 2

        elif e2.is_line():
            # 曲线->线
            # 或点->线
            if e1.is_curve():
                if not align:
                    v_rotation = p2 - p1
                else:
                    v_rotation = (
                        Vector((1.0, 0.0))
                        if alignment == "HORIZONTAL"
                        else Vector((0.0, 1.0))
                    )
                if v_rotation.length != 0:
                    angle = v_rotation.angle_signed(x_axis)
                
                mat_rot = Matrix.Rotation(angle, 2, "Z")
                v_translation = (p2 + p1) / 2
            else:
                assert isinstance(e1, SlvsPoint2D)
                orig = e2.p1.co
                end = e2.p2.co
                vec = end - orig
                angle = (math.tau / 4) + range_2pi(math.atan2(vec[1], vec[0]))
                mat_rot = Matrix.Rotation(angle, 2, "Z")
                p1 = p1 - orig
                v_translation = orig + (p1 + p1.project(vec)) / 2

        mat_local = Matrix.Translation(v_translation.to_3d()) @ mat_rot.to_4x4()
        return sketch.wp.matrix_basis @ mat_local

    def _get_init_value(self, alignment):
        """获取初始距离值（根据当前几何）"""
        e1, e2 = self.entity1, self.entity2

        if e1.is_3d():
            return (e1.location - e2.location).length

        if e1.is_line():
            return _get_aligned_distance(e1.p1, e1.p2, alignment)
        if type(e1) in CURVE:
            centerpoint = e1.ct.co
            if isinstance(e2, SlvsLine2D):
                endpoint, _ = intersect_point_line(centerpoint, e2.p1.co, e2.p2.co)
            else:
                assert isinstance(e2, SlvsPoint2D)
                endpoint = e2.co
            return (centerpoint - endpoint).length - e1.radius
        if isinstance(e2, SlvsWorkplane):
            # 返回到平面的有符号距离
            return distance_point_to_plane(e1.co, e2.p1.co, e2.normal)
        if type(e2) in LINE:
            orig = e2.p1.co
            end = e2.p2.co - orig
            p1 = e1.co - orig

            # 注意：来自 solvespace 文档的注释：
            # 当约束点到平面、点到平面面、或工作平面中点到线的距离时，
            # 距离是有符号的。距离可以是正或负，取决于点在平面的哪一侧。
            # 在草图上距离总是显示为正；要切换到另一侧，输入负值。
            return math.copysign(
                (p1 - (p1).project(end)).length,
                get_side_of_line(e2.p1.co, e2.p2.co, e1.co),
            )

        return _get_aligned_distance(e1, e2, alignment)

    def init_props(self, **kwargs):
        """初始化属性（从当前几何获取默认值）"""

        # 注意：通过 kwargs 传入的 Flip 目前被忽略
        alignment = kwargs.get("align")
        retval = {}

        value = kwargs.get("value", self._get_init_value(alignment))

        if self.use_flipping() and value < 0:
            value = abs(value)
            retval["flip"] = not self.flip

        retval["value"] = value
        retval["align"] = alignment
        return retval

    def text_inside(self, ui_scale):
        """判断文本是否应绘制在尺寸内部"""
        return (ui_scale * abs(self.draw_outset)) < self.value / 2

    def update_draw_offset(self, pos, ui_scale):
        """更新绘制偏移量"""
        self.draw_offset = pos[1] / ui_scale
        self.draw_outset = pos[0] / ui_scale

    def draw_props(self, layout):
        """绘制属性面板"""
        sub = super().draw_props(layout)

        row = sub.row()
        row.enabled = self.use_flipping()
        row.prop(self, "flip")

        sub.label(text="对齐：")
        row = sub.row()
        row.enabled = self.use_align()
        row.prop(self, "align", text="")

        if preferences.is_experimental():
            sub.prop(self, "draw_offset")

        return sub

    def value_placement(self, context):
        """计算约束值在3D视图中的显示位置"""
        region = context.region
        rv3d = context.space_data.region_3d
        ui_scale = context.preferences.system.ui_scale

        offset = ui_scale * self.draw_offset
        outset = ui_scale * self.draw_outset
        coords = self.matrix_basis() @ Vector((outset, offset, 0))
        return location_3d_to_region_2d(region, rv3d, coords)


slvs_entity_pointer(SlvsDistance, "entity1")
slvs_entity_pointer(SlvsDistance, "entity2")
slvs_entity_pointer(SlvsDistance, "sketch")

register, unregister = register_classes_factory((SlvsDistance,))