import logging

from bpy.types import Operator, Context
from bpy.props import FloatProperty

from ..model.utilities import update_pointers
from ..solver import solve_system
from ..declarations import Operators
from ..stateful_operator.utilities.register import register_stateops_factory
from .base_constraint import GenericConstraintOp
from ..utilities.select import deselect_all
from ..utilities.view import refresh
from ..solver import solve_system

from ..model.coincident import SlvsCoincident
from ..model.equal import SlvsEqual
from ..model.vertical import SlvsVertical
from ..model.horizontal import SlvsHorizontal
from ..model.parallel import SlvsParallel
from ..model.perpendicular import SlvsPerpendicular
from ..model.tangent import SlvsTangent
from ..model.midpoint import SlvsMidpoint
from ..model.ratio import SlvsRatio

logger = logging.getLogger(__name__)


def merge_points(context, duplicate, target):
    """合并重复的点，将重复点的引用更新为目标点"""
    update_pointers(context.scene, duplicate.slvs_index, target.slvs_index)
    context.scene.sketcher.entities.remove(duplicate.slvs_index)


class VIEW3D_OT_slvs_add_coincident(Operator, GenericConstraintOp):
    """添加重合约束"""

    bl_idname = Operators.AddCoincident
    bl_label = "重合"
    bl_options = {"UNDO", "REGISTER"}

    type = "COINCIDENT"

    def handle_merge(self, context):
        """处理点的合并：如果两个实体都是点且满足条件，则合并"""
        points = self.entity1, self.entity2

        if not all([e.is_point() for e in points]):
            return False

        for p1, p2 in (points, reversed(points)):
            if p1.origin:
                continue
            if p1.fixed:
                continue

            merge_points(context, p1, p2)
            solve_system(context, context.scene.sketcher.active_sketch)
            break
        return True

    def main(self, context: Context):
        # 隐式合并点
        if self.handle_merge(context):
            return True

        if not self.exists(context, SlvsCoincident):
            self.target = context.scene.sketcher.constraints.add_coincident(
                self.entity1,
                self.entity2,
                sketch=self.sketch,
            )
        return super().main(context)


class VIEW3D_OT_slvs_add_equal(Operator, GenericConstraintOp):
    """添加相等约束"""

    bl_idname = Operators.AddEqual
    bl_label = "相等"
    bl_options = {"UNDO", "REGISTER"}

    type = "EQUAL"

    def main(self, context):
        if not self.exists(context, SlvsEqual):
            self.target = context.scene.sketcher.constraints.add_equal(
                self.entity1,
                self.entity2,
                sketch=self.sketch,
            )

        return super().main(context)


class VIEW3D_OT_slvs_add_vertical(Operator, GenericConstraintOp):
    """添加竖直约束"""

    bl_idname = Operators.AddVertical
    bl_label = "竖直"
    bl_options = {"UNDO", "REGISTER"}

    type = "VERTICAL"

    def main(self, context):
        if not self.exists(context, SlvsVertical):
            self.target = context.scene.sketcher.constraints.add_vertical(
                self.entity1,
                entity2=self.entity2,
                sketch=self.sketch,
            )

        return super().main(context)


class VIEW3D_OT_slvs_add_horizontal(Operator, GenericConstraintOp):
    """添加水平约束"""

    bl_idname = Operators.AddHorizontal
    bl_label = "水平"
    bl_options = {"UNDO", "REGISTER"}

    type = "HORIZONTAL"

    def main(self, context):
        if not self.exists(context, SlvsHorizontal):
            self.target = context.scene.sketcher.constraints.add_horizontal(
                self.entity1,
                entity2=self.entity2,
                sketch=self.sketch,
            )

        return super().main(context)


class VIEW3D_OT_slvs_add_parallel(Operator, GenericConstraintOp):
    """添加平行约束"""

    bl_idname = Operators.AddParallel
    bl_label = "平行"
    bl_options = {"UNDO", "REGISTER"}

    type = "PARALLEL"

    def main(self, context):
        if not self.exists(context, SlvsParallel):
            self.target = context.scene.sketcher.constraints.add_parallel(
                self.entity1,
                self.entity2,
                sketch=self.sketch,
            )

        return super().main(context)


class VIEW3D_OT_slvs_add_perpendicular(Operator, GenericConstraintOp):
    """添加垂直约束（相互垂直）"""

    bl_idname = Operators.AddPerpendicular
    bl_label = "垂直"
    bl_options = {"UNDO", "REGISTER"}

    type = "PERPENDICULAR"

    def main(self, context):
        if not self.exists(context, SlvsPerpendicular):
            self.target = context.scene.sketcher.constraints.add_perpendicular(
                self.entity1,
                self.entity2,
                sketch=self.sketch,
            )

        return super().main(context)


class VIEW3D_OT_slvs_add_tangent(Operator, GenericConstraintOp):
    """添加相切约束"""

    bl_idname = Operators.AddTangent
    bl_label = "相切"
    bl_options = {"UNDO", "REGISTER"}

    type = "TANGENT"

    def main(self, context):
        if not self.exists(context, SlvsTangent):
            self.target = context.scene.sketcher.constraints.add_tangent(
                self.entity1,
                self.entity2,
                sketch=self.sketch,
            )

        return super().main(context)


class VIEW3D_OT_slvs_add_midpoint(Operator, GenericConstraintOp):
    """添加中点约束"""

    bl_idname = Operators.AddMidPoint
    bl_label = "中点"
    bl_options = {"UNDO", "REGISTER"}

    type = "MIDPOINT"

    def main(self, context):
        if not self.exists(context, SlvsMidpoint):
            self.target = context.scene.sketcher.constraints.add_midpoint(
                self.entity1,
                self.entity2,
                sketch=self.sketch,
            )

        return super().main(context)


class VIEW3D_OT_slvs_add_ratio(Operator, GenericConstraintOp):
    """添加比例约束"""

    bl_idname = Operators.AddRatio
    bl_label = "比例"
    bl_options = {"UNDO", "REGISTER"}

    value: FloatProperty(
        name="比例",
        subtype="UNSIGNED",
        options={"SKIP_SAVE"},
        min=0.0,
        precision=5,
    )
    type = "RATIO"
    property_keys = ("value",)

    def main(self, context):
        if not self.exists(context, SlvsRatio):
            self.target = context.scene.sketcher.constraints.add_ratio(
                self.entity1,
                self.entity2,
                sketch=self.sketch,
                init=not self.initialized,
                **self.get_settings(),
            )

        return super().main(context)


class VIEW3D_OT_slvs_add_symmetry(Operator, GenericConstraintOp):
    """添加对称约束"""

    bl_idname = Operators.AddSymmetry
    bl_label = "对称"
    bl_options = {"UNDO", "REGISTER"}

    type = "SYMMETRY"

    def main(self, context):
        if not self.exists(context, SlvsRatio):
            self.target = context.scene.sketcher.constraints.add_symmetry(
                self.entity1,
                self.entity2,
                self.entity3,
                sketch=self.sketch,
            )

        return super().main(context)


constraint_operators = (
    VIEW3D_OT_slvs_add_coincident,
    VIEW3D_OT_slvs_add_equal,
    VIEW3D_OT_slvs_add_vertical,
    VIEW3D_OT_slvs_add_horizontal,
    VIEW3D_OT_slvs_add_parallel,
    VIEW3D_OT_slvs_add_perpendicular,
    VIEW3D_OT_slvs_add_tangent,
    VIEW3D_OT_slvs_add_midpoint,
    VIEW3D_OT_slvs_add_ratio,
    VIEW3D_OT_slvs_add_symmetry,
)

register, unregister = register_stateops_factory(constraint_operators)