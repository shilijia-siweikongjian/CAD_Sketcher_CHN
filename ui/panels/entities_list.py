from bpy.types import Context

from .. import declarations
from . import VIEW3D_PT_sketcher_base


class VIEW3D_PT_sketcher_entities(VIEW3D_PT_sketcher_base):
    """
    实体面板：显示草图中的实体列表。
    可交互操作。
    """

    bl_label = "实体"
    bl_idname = declarations.Panels.SketcherEntities
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: Context):
        layout = self.layout
        box = layout.box()
        col = box.column(align=True)
        col.scale_y = 0.8

        sketch = context.scene.sketcher.active_sketch
        for e in context.scene.sketcher.entities.all:
            if not e.is_active(sketch):
                continue
            if e.is_sketch():
                continue

            row = col.row()
            row.alert = e.selected

            # 选择操作符
            props = row.operator(
                declarations.Operators.Select,
                text="",
                emboss=False,
                icon=("RADIOBUT_ON" if e.selected else "RADIOBUT_OFF"),
            )
            props.mode = "TOGGLE"
            props.index = e.slvs_index
            props.highlight_hover = True

            # 可见性切换
            row.prop(
                e,
                "visible",
                icon_only=True,
                icon=("HIDE_OFF" if e.visible else "HIDE_ON"),
                emboss=False,
            )

            row.prop(e, "name", text="")

            # 上下文菜单
            props = row.operator(
                declarations.Operators.ContextMenu,
                text="",
                icon="OUTLINER_DATA_GP_LAYER",
                emboss=False,
            )
            props.highlight_hover = True
            props.highlight_active = True
            props.index = e.slvs_index

            # 删除操作符
            props = row.operator(
                declarations.Operators.DeleteEntity,
                text="",
                icon="X",
                emboss=False,
            )
            props.index = e.slvs_index
            props.highlight_hover = True

            # 属性
            if e.props:
                row_props = col.row()
                row_props.alignment = "RIGHT"
                for entity_prop in e.props:
                    row_props.prop(e, entity_prop, text="")
                col.separator()