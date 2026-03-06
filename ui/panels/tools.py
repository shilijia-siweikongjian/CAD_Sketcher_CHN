from bpy.types import Context

from .. import declarations
from .. import icon_manager
from ...utilities.preferences import is_experimental
from . import VIEW3D_PT_sketcher_base


class VIEW3D_PT_sketcher_tools(VIEW3D_PT_sketcher_base):
    """
    工具面板：列出用于草绘的有用工具
    """

    bl_label = "工具"
    bl_idname = declarations.Panels.SketcherTools
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: Context):
        layout = self.layout

        # 约束
        layout.label(text="约束：")
        col = layout.column(align=True)

        for op in declarations.ConstraintOperators:
            col.operator(op, icon_value=icon_manager.get_constraint_icon(op))

        layout.separator()

        # 绘制
        layout.label(text="绘制：")
        layout.prop(context.scene.sketcher, "use_construction")

        # 节点修改器操作符
        if is_experimental():
            layout.label(text="节点工具：")
            col = layout.column(align=True)
            #col.operator(declarations.Operators.NodeFill)
            col.operator(declarations.Operators.NodeExtrude)
            col.operator(declarations.Operators.NodeArrayLinear)