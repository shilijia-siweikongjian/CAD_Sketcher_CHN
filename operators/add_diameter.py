import logging

from bpy.types import Operator
from bpy.props import FloatProperty, BoolProperty

from ..declarations import Operators
from ..stateful_operator.utilities.register import register_stateops_factory
from .base_constraint import GenericConstraintOp

from ..model.diameter import SlvsDiameter

logger = logging.getLogger(__name__)


class VIEW3D_OT_slvs_add_diameter(Operator, GenericConstraintOp):
    """添加一个直径约束"""

    bl_idname = Operators.AddDiameter
    bl_label = "直径"
    bl_options = {"UNDO", "REGISTER"}

    # 半径或直径
    value: FloatProperty(
        name="尺寸",
        subtype="DISTANCE",
        unit="LENGTH",
        precision=5,
        options={"SKIP_SAVE"},
    )
    setting: BoolProperty(name="使用半径")
    type = "DIAMETER"
    property_keys = ("value", "setting")

    def main(self, context):
        if not self.exists(context, SlvsDiameter):
            self.target = context.scene.sketcher.constraints.add_diameter(
                self.entity1,
                sketch=self.sketch,
                init=not self.initialized,
                **self.get_settings(),
            )

        return super().main(context)


register, unregister = register_stateops_factory((VIEW3D_OT_slvs_add_diameter,))