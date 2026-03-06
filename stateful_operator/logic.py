import bpy
from bpy.props import IntProperty, BoolProperty
from bpy.types import Context, Event
from mathutils import Vector

from .state_machine import _StateMachineMixin
from .utilities.generic import to_list
from .utilities.description import state_desc, stateful_op_desc
from .utilities.keymap import get_key_map_desc, is_numeric_input, is_unit_input
from .utilities.numeric import NumericInput

from typing import Optional, Any

# 重新导出，以便任何从 `.logic import _NumericInput` 的代码继续工作。
_NumericInput = NumericInput


class StatefulOperatorLogic(_StateMachineMixin):
    """有状态操作符的行为：数值输入、模态循环、撤销、连续绘制。

    继承自 ``_StateMachineMixin`` 中的纯状态机。

    生命周期（模态路径）
    ----------------------
    invoke → prefill_state_props (可选) → 模态循环：
        modal → evaluate_state → [next_state | _end | do_continuous_draw]

    生命周期（重做/执行路径）
    -----------------------------
    execute → redo_states → main → _end
    """

    state_index: IntProperty(options={"HIDDEN", "SKIP_SAVE"})
    wait_for_input: BoolProperty(options={"HIDDEN", "SKIP_SAVE"}, default=True)
    continuous_draw: BoolProperty(name="连续绘制", default=False)

    executed = False
    # 状态首次运行时的屏幕坐标——供 state_func 用于增量/缩放
    state_init_coords = None
    _last_coords = Vector((0, 0))
    _undo = False
    _state_snapshot = None

    # -------------------------------------------------------------------------
    # 快照/撤销钩子（在子类中重写）
    # -------------------------------------------------------------------------

    def create_snapshot(self, context: Context) -> Any:
        """返回状态的快照，以便在取消/撤销时恢复。

        返回 ``None`` 将回退到 Blender 的撤销系统。
        """
        return None

    def restore_snapshot(self, context: Context, snapshot: Any) -> None:
        """从 ``create_snapshot`` 生成的快照中恢复状态。"""
        pass

    def on_before_redo_states(self, context: Context):
        """在撤销/重做循环中的 ``redo_states`` 之前调用。

        重写此方法以清除必须重建的临时状态（例如绘制处理程序使用的实体忽略列表）。
        """
        pass

    # -------------------------------------------------------------------------
    # 状态转换（依赖于数值 + 状态文本——保留在此处）
    # -------------------------------------------------------------------------

    def set_state(self, context: Context, index: int):
        self.state_index = index
        self.init_numeric(False)
        self.set_status_text(context)

    def next_state(self, context: Context):
        self._undo = False
        self.state_init_coords = None
        i = self.state_index
        if (i + 1) >= len(self.get_states()):
            return False
        self.set_state(context, i + 1)
        return True

    # -------------------------------------------------------------------------
    # 数值输入——委托给 self._numeric (NumericInput)
    # -------------------------------------------------------------------------

    def set_status_text(self, context: Context):
        state = self.state
        desc = (
            state.description(self, state)
            if callable(state.description)
            else state.description
        )

        msg = state_desc(state.name, desc, state.types)
        if self._numeric.is_active:
            prop = self._numeric.prop
            index = self._numeric.substate_index
            array_length = prop.array_length if prop.array_length else 1

            if prop.type == "FLOAT":
                display = [0.0] * array_length
                for key in range(array_length):
                    val = self._numeric.get(key)
                    display[key] = val if val else 0.0
                display[index] = "*" + str(display[index])
                display_str = str(display).replace('"', "").replace("'", "")
                msg += "    {}: {}".format(prop.subtype, display_str)
            elif prop.type == "INT":
                msg += "    {}: {}".format(prop.subtype, self._numeric.current)

        context.workspace.status_text_set(msg)

    def check_numeric(self):
        """如果当前状态支持数值文本输入，返回 True。"""
        # TODO: 允许定义自定义逻辑
        props = self.get_property()
        if not props or len(props) > 1:
            return False
        prop_name = props[0]
        if not prop_name:
            return False
        prop = self.properties.rna_type.properties.get(prop_name)
        if not prop:
            return False
        return prop.type in ("INT", "FLOAT")

    def init_numeric(self, is_numeric: bool) -> bool:
        self._numeric.reset()
        if not is_numeric:
            self._init_substate()
            return False
        ok = self.check_numeric()
        self._numeric.is_active = ok
        self._init_substate()
        return ok

    def _init_substate(self):
        """解析当前状态的 RNA 属性并将其缓存在 _numeric 上。"""
        props = self.get_property()
        if not props or not props[0]:
            return
        prop = self.properties.rna_type.properties.get(props[0])
        self._numeric.init_substate(prop)

    # 公共包装器——为操作符子类保持 API 兼容性

    def iterate_substate(self):
        self._numeric.iterate()

    @property
    def numeric_input(self) -> str:
        return self._numeric.current

    @numeric_input.setter
    def numeric_input(self, value: str):
        self._numeric.current = value

    def evaluate_numeric_event(self, event: Event):
        self._numeric.evaluate_event(event)

    def validate_numeric_input(self, value: str) -> str:
        return self._numeric._validate(value)

    def get_numeric_value(self, context: Context, coords):
        """将当前数值文本缓冲区转换为类型化值（或列表）。"""
        prop_name = self.get_property()[0]
        prop = self.properties.rna_type.properties[prop_name]

        def parse_input(prop, raw):
            units = context.scene.unit_settings
            unit = prop.unit
            value = None
            if raw == "-":
                pass
            elif unit != "NONE":
                try:
                    value = bpy.utils.units.to_value(units.system, unit, raw)
                except ValueError:
                    return prop.default
                if prop.type == "INT":
                    value = int(value)
            elif prop.type == "FLOAT":
                value = float(raw)
            elif prop.type == "INT":
                value = int(raw)
            return prop.default if value is None else value

        def to_iterable(item):
            if hasattr(item, "__iter__") or hasattr(item, "__getitem__"):
                return list(item)
            return [item]

        size = max(1, self._numeric.substate_count or 0)

        # TODO: 如果不需要，不要评估交互值
        interactive_val = self._get_state_values(context, self.state, coords)
        if interactive_val is None:
            interactive_val = [None] * size
        else:
            interactive_val = to_iterable(interactive_val)

        storage = [None] * size
        result = [None] * size
        for sub_index in range(size):
            raw = self._numeric.get(sub_index)
            if raw:
                num = parse_input(prop, raw)
                result[sub_index] = num
                storage[sub_index] = num
            elif interactive_val[sub_index] is not None:
                result[sub_index] = interactive_val[sub_index]
            else:
                result[sub_index] = prop.default

        self.state_data["numeric_input"] = storage
        return result[0] if not self._numeric.substate_count else result

    # -------------------------------------------------------------------------
    # 选择预填充
    # -------------------------------------------------------------------------

    def prefill_state_props(self, context: Context):
        selected = self.gather_selection(context)

        while True:
            index = self.state_index
            state = self.state
            self.get_state_data(index)

            if not state.allow_prefill:
                break

            func = self.get_func(state, "parse_selection")
            result = func(context, selected, index=index)

            if result:
                if not self.next_state(context):
                    return {"FINISHED"}
                continue
            break
        return {"RUNNING_MODAL"}

    # -------------------------------------------------------------------------
    # 操作符生命周期——invoke / modal / execute / _end
    # -------------------------------------------------------------------------

    def check_event(self, event):
        is_confirm = event.type in ("LEFTMOUSE", "RET", "NUMPAD_ENTER")
        if is_confirm and event.value == "PRESS":
            return True
        if self.state_index == 0 and not self.wait_for_input:
            return not self._numeric.is_active
        if self.state.no_event:
            return True
        return False

    def invoke(self, context: Context, event: Event):
        self._state_data.clear()
        self._numeric = NumericInput()
        self._state_snapshot = self.create_snapshot(context)

        if hasattr(self, "init"):
            if not self.init(context, event):
                return self._end(context, False)

        retval = {"RUNNING_MODAL"}
        go_modal = True

        if is_numeric_input(event):
            if self.init_numeric(True):
                self._numeric.evaluate_event(event)
                self.evaluate_state(context, event, False)

        # wait_for_input=True：尊重选择以进行预填充，但等待左键
        elif self.wait_for_input:
            retval = self.prefill_state_props(context)
            if retval == {"FINISHED"}:
                go_modal = False
            if not self.executed and self.check_props():
                self.run_op(context)
                self.executed = True
            context.area.tag_redraw()

        self.set_status_text(context)

        if go_modal:
            context.window.cursor_modal_set("CROSSHAIR")
            context.window_manager.modal_handler_add(self)
            return retval

        succeede = retval == {"FINISHED"}
        # 注意：在此处推入撤销步骤会导致重做后重复的约束。
        return self._end(context, succeede)

    def execute(self, context: Context):
        self._numeric = NumericInput()
        self.redo_states(context)
        ok = self.main(context)
        return self._end(context, ok, skip_undo=True)

    def _handle_pass_through(self, context: Context, event: Event):
        if event.type in {"MIDDLEMOUSE", "WHEELUPMOUSE", "WHEELDOWNMOUSE", "MOUSEMOVE"}:
            return {"PASS_THROUGH"}
        return {"RUNNING_MODAL"}

    def modal(self, context: Context, event: Event):
        state = self.state
        event_triggered = self.check_event(event)
        coords = Vector((event.mouse_region_x, event.mouse_region_y))

        is_numeric_edit = self._numeric.is_active
        is_numeric_event = event.value == "PRESS" and is_numeric_input(event)

        if is_numeric_edit:
            if is_unit_input(event) and event.value == "PRESS":
                is_numeric_event = True
            elif event.type == "TAB" and event.value == "PRESS":
                self._numeric.iterate()
                self.set_status_text(context)
        elif is_numeric_event:
            is_numeric_edit = self.init_numeric(True)

        if event.type in {"RIGHTMOUSE", "ESC"}:
            return self._end(context, False)

        # HACK: 在模态内部调用 ops.ed.undo() 会触发虚假的 MOUSEMOVE。
        # 通过检查实际像素移动来过滤。
        mousemove_threshold = 0.1
        is_mousemove = (coords - self._last_coords).length > mousemove_threshold
        self._last_coords = coords

        if not event_triggered:
            if is_numeric_event:
                pass
            elif is_mousemove and is_numeric_edit:
                pass
            elif not state.interactive:
                return self._handle_pass_through(context, event)
            elif not is_mousemove:
                return self._handle_pass_through(context, event)

        # TODO: 当没有 state.property 时禁用数值输入
        if is_numeric_event:
            self._numeric.evaluate_event(event)
            self.set_status_text(context)

        return self.evaluate_state(context, event, event_triggered)

    # -------------------------------------------------------------------------
    # evaluate_state 及其子步骤
    # -------------------------------------------------------------------------

    def _get_state_values(self, context: Context, state, coords):
        """调用状态的 state_func 并返回原始位置/值，或 None。"""
        cb = self.get_func(state, "state_func")
        if not cb:
            return None
        return cb(context, coords)

    def _pick_hovered(self, context: Context, coords, state, is_numeric):
        """尝试拾取光标下的现有元素。

        返回 ``(is_picked, pointer_values)``——仅当 is_picked 为 True 时 pointer_values 有效。
        """
        if is_numeric or not state.pointer:
            return False, None
        pick = self.get_func(state, "pick_element")
        retval = pick(context, coords)
        if retval is not None:
            return True, to_list(retval)
        return False, None

    def _resolve_values(self, context: Context, coords, state, is_numeric, is_picked):
        """通过 state_func 或数值输入计算属性值。

        返回 ``(values, ok)``——ok 表示状态可以前进。
        当生成值时在 self 上设置属性并标记 ``_undo``。
        """
        ok = False
        values = []
        use_create = state.use_create and self.has_func(state, "create_element")
        if not use_create or is_picked:
            return values, ok

        if is_numeric:
            values = [self.get_numeric_value(context, coords)]
        else:
            values = to_list(self._get_state_values(context, state, coords))

        if values:
            props = self.get_property()
            if props:
                for i, v in enumerate(values):
                    setattr(self, props[i], v)
                self._undo = True
                ok = not state.pointer

        return values, ok

    def _apply_undo(self, context: Context):
        """恢复到快照或 Blender 撤销，然后重放 redo_states。"""
        if self._state_snapshot is not None:
            self.restore_snapshot(context, self._state_snapshot)
            self.on_before_redo_states(context)
            self.redo_states(context)
        else:
            bpy.ops.ed.undo_push(message="重做: " + self.bl_label)
            bpy.ops.ed.undo()
            self.on_before_redo_states(context)
            self.redo_states(context)
        self._undo = False

    def evaluate_state(self, context: Context, event, triggered):
        state = self.state
        data = self.state_data
        is_numeric = self._numeric.is_active
        coords = Vector((event.mouse_region_x, event.mouse_region_y))

        if self.state_init_coords is None:
            self.state_init_coords = coords

        is_picked, pointer_values = self._pick_hovered(context, coords, state, is_numeric)
        values, ok = self._resolve_values(context, coords, state, is_numeric, is_picked)

        # 解析状态指针
        if state.pointer:
            if is_picked:
                data["is_existing_entity"] = True
                self.set_state_pointer(pointer_values, implicit=True)
                ok = True
            elif values:
                # 指针将在 redo_states 期间通过 create_element 填充
                data["is_existing_entity"] = False
                ok = True

        if self._undo:
            self._apply_undo(context)

        succeede = False
        if self.check_props():
            succeede = self.run_op(context)
            self._undo = True

        # 状态转换
        if triggered and ok:
            if not self.next_state(context):
                if self.check_continuous_draw():
                    self.do_continuous_draw(context)
                else:
                    return self._end(context, succeede)
            if is_numeric:
                # 立即运行下一个状态一次，以便在不移动鼠标的情况下更新几何体
                self.evaluate_state(context, event, False)

        context.area.tag_redraw()

        if triggered and not ok:
            # 在无效目标上触发——取消以避免混淆
            return self._end(context, False)

        if triggered or is_numeric:
            return {"RUNNING_MODAL"}
        return self._handle_pass_through(context, event)

    # -------------------------------------------------------------------------
    # 操作符执行辅助函数
    # -------------------------------------------------------------------------

    def run_op(self, context: Context):
        if not hasattr(self, "main"):
            raise NotImplementedError(
                "有状态操作符必须定义 main 方法！"
            )
        retval = self.main(context)
        self.executed = True
        return retval

    def redo_states(self, context: Context):
        """为达到当前状态之前的所有状态重新创建非持久元素。"""
        for i, state in enumerate(self.get_states()):
            if i > self.state_index:
                # TODO: 不要依赖于活动状态；理想情况下可以返回
                break
            if state.pointer:
                data = self._state_data.get(i, {})
                is_existing_entity = data["is_existing_entity"]
                props = self.get_property(index=i)
                if props and not is_existing_entity:
                    create = self.get_func(state, "create_element")
                    ret_values = create(
                        context, [getattr(self, p) for p in props], state, data
                    )
                    self.set_state_pointer(to_list(ret_values), index=i, implicit=True)

    def _end(self, context, succeede, skip_undo=False):
        context.window.cursor_modal_restore()
        if hasattr(self, "fini"):
            self.fini(context, succeede)
        self.on_before_redo_states(context)
        context.workspace.status_text_set(None)

        if not succeede and not skip_undo:
            if self._state_snapshot is not None:
                self.restore_snapshot(context, self._state_snapshot)
            else:
                bpy.ops.ed.undo_push(message="取消: " + self.bl_label)
                bpy.ops.ed.undo()

        self._state_snapshot = None
        return {"FINISHED"} if succeede else {"CANCELLED"}

    # -------------------------------------------------------------------------
    # 连续绘制
    # -------------------------------------------------------------------------

    def check_continuous_draw(self):
        if self.continuous_draw:
            if not hasattr(self, "continue_draw") or self.continue_draw():
                return True
        return False

    def _reset_op(self):
        self.executed = False
        for i, s in enumerate(self.get_states()):
            if not s.pointer:
                continue
            self.set_state_pointer(None, index=i)
        self._state_data.clear()
        self._numeric = NumericInput()
        self._state_snapshot = None

    def _take_last_state_pointer(self):
        """返回 (last_index, implicit_values, type_metadata) 用于最后一个指针状态。"""
        for i, s in reversed(list(enumerate(self.get_states()))):
            if not s.pointer:
                continue
            last_type = self._state_data.get(i, {}).get("type")
            values = to_list(self.get_state_pointer(index=i, implicit=True))
            return i, values, last_type
        return None, [], None

    def do_continuous_draw(self, context):
        """完成当前线段并立即开始下一个。

        已完成线段的最后一个指针（例如线段端点）成为新线段的第一个指针，形成链。
        """
        self._end(context, True)
        bpy.ops.ed.undo_push(message=self.bl_label)

        # 在 _reset_op 清除状态之前保存端点
        last_index, values, last_type = self._take_last_state_pointer()

        self._reset_op()

        # 将保存的端点作为新线段的种子重新注入
        data = self.get_state_data(0)
        data["is_existing_entity"] = True
        if last_type:
            data["type"] = last_type
        self.set_state_pointer(values, index=0, implicit=True)
        self.set_state(context, 1)
        self._state_snapshot = self.create_snapshot(context)

    # -------------------------------------------------------------------------
    # 类级描述
    # -------------------------------------------------------------------------

    @classmethod
    def description(cls, context, _properties):
        states = [
            state_desc(s.name, s.description, s.types)
            for s in cls.get_states_definition()
        ]
        descs = []
        hint = get_key_map_desc(context, cls.bl_idname)
        if hint:
            descs.append(hint)
        if cls.__doc__:
            descs.append(cls.__doc__)
        return stateful_op_desc(" ".join(descs), *states)