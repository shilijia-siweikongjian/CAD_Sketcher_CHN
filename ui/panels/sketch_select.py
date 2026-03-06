from bpy.types import Context, UILayout

from .. import declarations
from . import VIEW3D_PT_sketcher_base


def sketch_selector(
    context: Context,
    layout: UILayout,
):
    row = layout.row(align=True)
    row.scale_y = 1.8
    active_sketch = context.scene.sketcher.active_sketch

    if not active_sketch:
        row.operator(
            declarations.Operators.AddSketch,
            icon="ADD"
        ).wait_for_input = True

    else:
        row.operator(
            declarations.Operators.SetActiveSketch,
            text="离开：" + active_sketch.name,
            icon="BACK",
            depress=True,
        ).index = -1
        row.active = True

    row.operator(declarations.Operators.Update, icon="FILE_REFRESH", text="")


class VIEW3D_PT_sketcher(VIEW3D_PT_sketcher_base):
    """选择要进入的草图的菜单"""

    bl_label = "草图"
    bl_idname = declarations.Panels.Sketcher

    def draw(self, context: Context):
        layout = self.layout

        sketch_selector(context, layout)
        sketch = context.scene.sketcher.active_sketch
        layout.use_property_split = True
        layout.use_property_decorate = False

        if sketch:
            # 草图已选中，显示草图自身的信息
            row = layout.row()
            row.alignment = "CENTER"
            row.scale_y = 1.2

            if sketch.solver_state != "OKAY":
                state = sketch.get_solver_state()
                row.operator(
                    declarations.Operators.ShowSolverState,
                    text=state.name,
                    icon=state.icon,
                    emboss=False,
                ).index = sketch.slvs_index
            else:
                dof = sketch.dof
                dof_ok = dof <= 0
                dof_msg = (
                    "草图完全定义"
                    if dof_ok
                    else "自由度：" + str(dof)
                )
                dof_icon = "CHECKMARK" if dof_ok else "ERROR"
                row.label(text=dof_msg, icon=dof_icon)

            layout.separator()

            row = layout.row()
            row.prop(sketch, "name")
            layout.prop(sketch, "convert_type")

            if sketch.convert_type == "MESH":
                layout.prop(sketch, "curve_resolution")
            if sketch.convert_type != "NONE":
                layout.prop(sketch, "fill_shape")

            layout.operator(
                declarations.Operators.DeleteEntity,
                text="删除草图",
                icon="X",
            ).index = sketch.slvs_index

        else:
            # 无活动草图，显示可用草图列表
            layout.template_list(
                "VIEW3D_UL_sketches",
                "",
                context.scene.sketcher.entities,
                "sketches",
                context.scene.sketcher,
                "ui_active_sketch",
                item_dyntip_propname="name",
            )