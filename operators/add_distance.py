import logging

from bpy.types import Operator, Context
from bpy.props import BoolProperty, FloatProperty, EnumProperty

from .base_constraint import GenericConstraintOp
from ..model.distance import align_items
from ..declarations import Operators
from ..stateful_operator.utilities.register import register_stateops_factory

from ..model.distance import SlvsDistance
from ..model.line_2d import SlvsLine2D
from ..model.point_2d import SlvsPoint2D
from ..model.types import SlvsPoint3D
from ..model.types import SlvsLine3D

logger = logging.getLogger(__name__)


class VIEW3D_OT_slvs_add_distance(Operator, GenericConstraintOp):
    """添加一个距离约束"""

    bl_idname = Operators.AddDistance
    bl_label = "距离"
    bl_options = {"UNDO", "REGISTER"}

    value: FloatProperty(
        name="距离",
        subtype="DISTANCE",
        unit="LENGTH",
        min=0.0,
        precision=5,
        options={"SKIP_SAVE"},
    )
    align: EnumProperty(name="对齐", items=align_items)
    flip: BoolProperty(name="翻转")
    type = "DISTANCE"
    property_keys = ("value", "align", "flip")

    def main(self, context):
        # 如果实体1是2D线且实体2为空，则将其端点作为两个实体处理
        if isinstance(self.entity1, SlvsLine2D) and self.entity2 is None:
            dependencies = self.entity1.dependencies()
            if (isinstance(dependencies[0], SlvsPoint2D) and
                    isinstance(dependencies[1], SlvsPoint2D)):
                # 循环将 self.entity1 和 self.entity2 的值从线实体改为其端点
                for i in range(0, 2):
                    state_data = self.get_state_data(i)
                    state_data["hovered"] = -1
                    state_data["type"] = type(dependencies[i])
                    state_data["is_existing_entity"] = True
                    state_data["entity_index"] = dependencies[i].slvs_index
                self.next_state(context)  # 结束用户选择，不需要第二个实体

        # 根据实体类型确定允许的最大约束数量
        if (isinstance(self.entity1, (SlvsPoint3D, SlvsLine3D)) or
                isinstance(self.entity2, (SlvsPoint3D, SlvsLine3D))):
            max_constraints = 3
        elif ((isinstance(self.entity1, SlvsLine2D) and self.entity2 is None) or
                isinstance(self.entity1, SlvsPoint2D) and isinstance(self.entity2, SlvsPoint2D)):
            max_constraints = 2
        else:
            max_constraints = 1

        # 检查是否已存在同类型约束（不超过最大数量）
        if not self.exists(context, SlvsDistance, max_constraints):
            self.target = context.scene.sketcher.constraints.add_distance(
                self.entity1,
                self.entity2,
                sketch=self.sketch,
                init=not self.initialized,
                **self.get_settings(),
            )
        return super().main(context)

    def fini(self, context: Context, succeede: bool):
        super().fini(context, succeede)
        if hasattr(self, "target"):
            # 设置绘制偏移量，基于视图距离
            self.target.draw_offset = 0.05 * context.region_data.view_distance

    def draw(self, context: Context):
        if not hasattr(self, "target"):
            return

        layout = self.layout
        c = self.target

        row = layout.row()
        row.prop(self, "value")

        row = layout.row()
        row.enabled = c.use_align()
        row.prop(self, "align")

        row = layout.row()
        row.enabled = c.use_flipping()
        row.prop(self, "flip")


register, unregister = register_stateops_factory((VIEW3D_OT_slvs_add_distance,))