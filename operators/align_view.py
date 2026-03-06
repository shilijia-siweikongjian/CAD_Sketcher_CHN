import bpy
import mathutils

import time
import logging

from ..declarations import Operators
from ..stateful_operator.utilities.register import register_stateops_factory

logger = logging.getLogger(__name__)


START_TIME = 0
DURATION = 1.0
REGION3D = None
START_LOCATION = None
START_ROTATION = None
TARGET_MATRIX = None


def animate_viewport():
    global REGION3D
    
    # 检查 REGION3D 是否仍然可用
    if REGION3D is None:
        return None  # 停止动画
    
    # 计算经过的时间
    elapsed_time = time.time() - START_TIME
    t = min(elapsed_time / DURATION, 1.0)  # 将时间归一化到 [0, 1]

    # 插值位置和旋转
    REGION3D.view_location = START_LOCATION.lerp(TARGET_MATRIX.translation, t)
    REGION3D.view_rotation = START_ROTATION.slerp(TARGET_MATRIX.to_quaternion(), t)

    # 如果动画未完成，继续
    if t < 1.0:
        return 0.02  # 继续定时器



class View3D_OT_slvs_align_view(bpy.types.Operator):
    """将视图对齐到给定草图"""

    bl_idname = Operators.AlignView
    bl_label = "对齐视图到草图"
    bl_description = "将视图对齐到指定草图"
    bl_options = {'UNDO'}

    sketch_index: bpy.props.IntProperty(
        name="草图索引",
        default=-1,
        description="要对齐的草图索引，-1 表示默认视图"
    )
    use_active: bpy.props.BoolProperty(
        name="使用活动草图",
        default=False,
        description="使用活动草图而不是索引"
    )
    duration: bpy.props.FloatProperty(
        name="时长",
        default=0.3,
        min=0,
        max=2,
        description="动画持续时间（秒）"
    )

    def execute(self, context):
        global REGION3D, START_LOCATION, START_ROTATION, TARGET_MATRIX, START_TIME, DURATION

        REGION3D = context.region_data
        DURATION = self.duration

        # 检查 region_data 是否可用
        if REGION3D is None:
            self.report({'WARNING'}, "没有可用的3D视图用于对齐")
            return {'CANCELLED'}

        # 存储当前的位置和旋转
        START_LOCATION = REGION3D.view_location.copy()
        START_ROTATION = REGION3D.view_rotation.copy()

        sketcher = context.scene.sketcher
        sketch = sketcher.active_sketch if self.use_active else sketcher.entities.get(self.sketch_index)

        if sketch:
            TARGET_MATRIX = sketch.wp.matrix_basis
            REGION3D.view_perspective = "ORTHO"
        else:
            # 恢复视图到默认状态
            TARGET_MATRIX = mathutils.Quaternion((0.7123758792877197, 0.4410620927810669, 0.28735825419425964, 0.4641229212284088)).to_matrix().to_4x4()
            REGION3D.view_perspective = "PERSP"

        # 开始动画
        START_TIME = time.time()
        bpy.app.timers.register(animate_viewport)

        return {'FINISHED'}


register, unregister = register_stateops_factory((View3D_OT_slvs_align_view,))