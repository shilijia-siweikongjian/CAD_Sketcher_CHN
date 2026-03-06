import logging

import bpy
from bpy.types import Operator, Context, Event

from ..model.types import SlvsWorkplane
from ..declarations import Operators
from ..stateful_operator.utilities.register import register_stateops_factory
from ..stateful_operator.state import state_from_args
from .base_3d import Operator3d
from .utilities import activate_sketch, switch_sketch_mode


logger = logging.getLogger(__name__)


# TODO:
# - Draw sketches
class View3D_OT_slvs_add_sketch(Operator, Operator3d):
    """添加一个草图"""

    bl_idname = Operators.AddSketch
    bl_label = "添加草图"
    bl_options = {"UNDO"}

    sketch_state1_doc = ["工作平面", "选择一个工作平面作为草图的基础。"]

    states = (
        state_from_args(
            sketch_state1_doc[0],
            description=sketch_state1_doc[1],
            pointer="wp",
            types=(SlvsWorkplane,),
            property=None,
            use_create=False,
        ),
    )

    def prepare_origin_elements(self, context):
        context.scene.sketcher.entities.ensure_origin_elements(context)
        return True

    def init(self, context: Context, event: Event):
        switch_sketch_mode(self, context, to_sketch_mode=True)
        self.prepare_origin_elements(context)
        bpy.ops.ed.undo_push(message="确保原点元素存在")
        context.scene.sketcher.show_origin = True
        return True

    def main(self, context: Context):
        sse = context.scene.sketcher.entities
        sketch = sse.add_sketch(self.wp)

        # 在原点添加一个点
        # 注：也许可以创建一个主原点的参考实体？
        p = sse.add_point_2d((0.0, 0.0), sketch)
        p.fixed = True

        activate_sketch(context, sketch.slvs_index, self)
        self.target = sketch
        return True

    def fini(self, context: Context, succeed: bool):
        context.scene.sketcher.show_origin = False
        if hasattr(self, "target"):
            logger.debug("添加：{}".format(self.target))

        if succeed:
            self.wp.visible = False
        else:
            switch_sketch_mode(self, context, to_sketch_mode=False)


register, unregister = register_stateops_factory((View3D_OT_slvs_add_sketch,))