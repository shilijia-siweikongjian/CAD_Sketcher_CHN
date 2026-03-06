from bpy.types import Context, UILayout

from .. import declarations
from .. import types
from . import VIEW3D_PT_sketcher_base


def draw_constraint_listitem(
    context: Context, layout: UILayout, constraint: types.GenericConstraint
):
    """
    在 ``layout`` 中为给定的 ``constraint`` 创建一行显示。
    """
    index = context.scene.sketcher.constraints.get_index(constraint)
    row = layout.row()

    # 可见/隐藏属性
    row.prop(
        constraint,
        "visible",
        icon_only=True,
        icon=("HIDE_OFF" if constraint.visible else "HIDE_ON"),
        emboss=False,
    )

    # 失败提示
    row.label(
        text="",
        icon=("ERROR" if constraint.failed else "CHECKMARK"),
    )

    # 标签
    row.prop(constraint, "name", text="")

    # 约束值
    middle_sub = row.row()

    for constraint_prop in constraint.props:
        middle_sub.prop(constraint, constraint_prop, text="")

    # 上下文菜单，显示约束名称
    props = row.operator(
        declarations.Operators.ContextMenu,
        text="",
        icon="OUTLINER_DATA_GP_LAYER",
        emboss=False,
    )
    props.type = constraint.type
    props.index = index
    props.highlight_hover = True
    props.highlight_active = True
    props.highlight_members = True

    # 删除操作符
    props = row.operator(
        declarations.Operators.DeleteConstraint,
        text="",
        icon="X",
        emboss=False,
    )
    props.type = constraint.type
    props.index = index
    props.highlight_hover = True
    props.highlight_members = True


class VIEW3D_PT_sketcher_constraints(VIEW3D_PT_sketcher_base):
    """
    约束面板：显示草图中的约束列表，可交互操作。
    """

    bl_label = "约束"
    bl_idname = declarations.Panels.SketcherConstraints
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: Context):
        layout = self.layout

        # 可见性操作符
        col = layout.column(align=True)
        col.operator_enum(
            declarations.Operators.SetAllConstraintsVisibility,
            "visibility",
        )

        # 尺寸约束
        layout.label(text="尺寸约束：")
        box = layout.box()
        col = box.column(align=True)
        col.scale_y = 0.8

        sketch = context.scene.sketcher.active_sketch
        for c in context.scene.sketcher.constraints.dimensional:
            if not c.is_active(sketch):
                continue
            draw_constraint_listitem(context, col, c)

        # 几何约束
        layout.label(text="几何约束：")
        box = layout.box()
        col = box.column(align=True)
        col.scale_y = 0.8

        sketch = context.scene.sketcher.active_sketch
        for c in context.scene.sketcher.constraints.geometric:
            if not c.is_active(sketch):
                continue
            draw_constraint_listitem(context, col, c)