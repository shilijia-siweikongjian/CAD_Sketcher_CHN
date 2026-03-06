import logging
import math

from bpy.types import Operator, Context, Event
from mathutils import Vector

from ..declarations import Operators
from ..stateful_operator.utilities.register import register_stateops_factory
from ..stateful_operator.state import state_from_args
from ..solver import solve_system
from ..utilities.math import pol2cart
from .base_2d import Operator2d
from .constants import types_point_2d
from .utilities import ignore_hover
from ..utilities.view import get_pos_2d

logger = logging.getLogger(__name__)


class View3D_OT_slvs_add_arc2d(Operator, Operator2d):
    """向活动草图添加一段圆弧"""

    bl_idname = Operators.AddArc2D
    bl_label = "添加2D圆弧"
    bl_options = {"REGISTER", "UNDO"}

    arc_state1_doc = ("圆心", "拾取或放置圆心点。")
    arc_state2_doc = ("起点", "拾取或放置起点。")
    arc_state3_doc = ("终点", "拾取或放置终点。")

    states = (
        state_from_args(
            arc_state1_doc[0],
            description=arc_state1_doc[1],
            pointer="ct",
            types=types_point_2d,
        ),
        state_from_args(
            arc_state2_doc[0],
            description=arc_state2_doc[1],
            pointer="p1",
            types=types_point_2d,
            allow_prefill=False,
        ),
        state_from_args(
            arc_state3_doc[0],
            description=arc_state3_doc[1],
            pointer="p2",
            types=types_point_2d,
            state_func="get_endpoint_pos",
            interactive=True,
        ),
    )

    def get_endpoint_pos(self, context: Context, coords):
        """根据鼠标位置计算终点坐标（保持半径与起点一致）"""
        mouse_pos = get_pos_2d(context, self.sketch.wp, coords)
        if mouse_pos is None:
            return None

        # 获取鼠标位置相对于圆心的角度
        ct = self.get_point(context, 0).co
        x, y = Vector(mouse_pos) - ct
        angle = math.atan2(y, x)

        # 根据起点到圆心的距离确定半径
        p1 = self.get_point(context, 1).co
        radius = (p1 - ct).length
        pos = pol2cart(radius, angle) + ct
        return pos

    def solve_state(self, context: Context, _event: Event):
        sketch = context.scene.sketcher.active_sketch
        solve_system(context, sketch=sketch)
        return True

    def main(self, context):
        ct, p1, p2 = (
            self.get_point(context, 0),
            self.get_point(context, 1),
            self.get_point(context, 2),
        )
        sketch = self.sketch
        sse = context.scene.sketcher.entities
        arc = sse.add_arc(sketch.wp.nm, ct, p1, p2, sketch)

        center = ct.co
        start = p1.co - center
        end = p2.co - center
        a = end.angle_signed(start)
        arc.invert_direction = a < 0

        ignore_hover(arc)
        self.target = arc
        if context.scene.sketcher.use_construction:
            self.target.construction = True
        return True

    def fini(self, context: Context, succeede: bool):
        if hasattr(self, "target"):
            logger.debug("添加：{}".format(self.target))
            self.solve_state(context, self.sketch)


register, unregister = register_stateops_factory((View3D_OT_slvs_add_arc2d,))