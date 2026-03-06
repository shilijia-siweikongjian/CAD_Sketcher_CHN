import logging

from bpy.types import Operator, Context
from bpy.props import FloatVectorProperty

from .. import global_data
from ..declarations import Operators
from ..stateful_operator.utilities.register import register_stateops_factory
from ..stateful_operator.state import state_from_args
from ..solver import solve_system
from .base_2d import Operator2d

logger = logging.getLogger(__name__)


class View3D_OT_slvs_add_point2d(Operator, Operator2d):
    """向活动草图添加一个点"""

    bl_idname = Operators.AddPoint2D
    bl_label = "添加2D点"
    bl_options = {"REGISTER", "UNDO"}

    p2d_state1_doc = ("坐标", "设置点在草图上的坐标。")

    coordinates: FloatVectorProperty(name="坐标", size=2, precision=5)

    states = (
        state_from_args(
            p2d_state1_doc[0],
            description=p2d_state1_doc[1],
            property="coordinates",
        ),
    )

    def main(self, context: Context):
        sketch = self.sketch
        self.target = context.scene.sketcher.entities.add_point_2d(
            self.coordinates, sketch
        )
        if context.scene.sketcher.use_construction:
            self.target.construction = True

        # 存储悬停实体用于自动重合，因为非交互式工具不会存储悬停信息
        hovered = global_data.hover
        if self._check_constrain(context, hovered):
            self.state_data["hovered"] = hovered

        self.add_coincident(context, self.target, self.state, self.state_data)
        return True

    def fini(self, context: Context, succeede: bool):
        if hasattr(self, "target"):
            logger.debug("添加：{}".format(self.target))

        if succeede:
            if self.has_coincident():
                solve_system(context, sketch=self.sketch)


register, unregister = register_stateops_factory((View3D_OT_slvs_add_point2d,))