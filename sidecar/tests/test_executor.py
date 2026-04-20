"""Tests for WorkflowExecutor — unit tests using mocked BrowserController."""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from engine.executor import WorkflowExecutor, ExecutionContext, _LoopBreak


@pytest.fixture
def mock_ctrl():
    ctrl = MagicMock()
    ctrl.get_url.return_value = "https://example.com/page"
    ctrl.get_element_text.return_value = "Hello"
    ctrl.get_element_attribute.return_value = "https://link.com"
    ctrl.get_element_count.return_value = 3
    ctrl.is_visible.return_value = True
    ctrl.extract_table.return_value = [["a", "b"], ["1", "2"]]
    ctrl.evaluate.return_value = "js_result"
    ctrl.get_cookie.return_value = [{"name": "sid", "value": "abc"}]
    ctrl.screenshot.return_value = "screenshot.png"
    return ctrl


@pytest.fixture
def executor(mock_ctrl):
    return WorkflowExecutor(mock_ctrl)


# --- Basic action tests ---

class TestBasicActions:
    def test_navigate(self, executor, mock_ctrl):
        wf = {"nodes": [{"type": "action", "action": "Navigate", "url": "https://test.com"}]}
        result = executor.execute(wf)
        assert result["success"]
        mock_ctrl.navigate.assert_called_once_with("https://test.com")

    def test_click(self, executor, mock_ctrl):
        wf = {"nodes": [{"type": "action", "action": "Click", "selector": "#btn"}]}
        result = executor.execute(wf)
        assert result["success"]
        mock_ctrl.click.assert_called_once_with("#btn")

    def test_type(self, executor, mock_ctrl):
        wf = {"nodes": [{"type": "action", "action": "Type", "selector": "#input", "value": "hello"}]}
        result = executor.execute(wf)
        assert result["success"]
        mock_ctrl.type_text.assert_called_once_with("#input", "hello")

    def test_get_text(self, executor, mock_ctrl):
        wf = {"nodes": [{"type": "action", "action": "GetText", "selector": ".el", "into": "$text"}]}
        result = executor.execute(wf)
        assert result["success"]
        assert result["variables"]["$text"] == "Hello"

    def test_get_url(self, executor, mock_ctrl):
        wf = {"nodes": [{"type": "action", "action": "GetURL", "into": "$url"}]}
        result = executor.execute(wf)
        assert result["success"]
        assert result["variables"]["$url"] == "https://example.com/page"

    def test_set_variable(self, executor):
        wf = {"nodes": [{"type": "action", "action": "SetVariable", "variable": "$x", "value": 42}]}
        result = executor.execute(wf)
        assert result["success"]
        assert result["variables"]["$x"] == 42

    def test_screenshot(self, executor, mock_ctrl):
        wf = {"nodes": [{"type": "action", "action": "Screenshot", "filename": "test.png"}]}
        result = executor.execute(wf)
        assert result["success"]
        mock_ctrl.screenshot.assert_called_once_with("test.png")

    def test_delay(self, executor):
        wf = {"nodes": [{"type": "action", "action": "Delay", "duration": "100ms"}]}
        result = executor.execute(wf)
        assert result["success"]

    def test_log(self, executor):
        wf = {"nodes": [{"type": "action", "action": "Log", "parts": ["test", "msg"]}]}
        result = executor.execute(wf)
        assert result["success"]

    def test_comment_noop(self, executor, mock_ctrl):
        wf = {"nodes": [{"type": "action", "action": "Comment"}]}
        result = executor.execute(wf)
        assert result["success"]

    def test_dblclick(self, executor, mock_ctrl):
        wf = {"nodes": [{"type": "action", "action": "DblClick", "selector": ".el"}]}
        result = executor.execute(wf)
        assert result["success"]
        mock_ctrl.dblclick.assert_called_once_with(".el")

    def test_hover(self, executor, mock_ctrl):
        wf = {"nodes": [{"type": "action", "action": "Hover", "selector": ".el"}]}
        result = executor.execute(wf)
        assert result["success"]
        mock_ctrl.hover.assert_called_once_with(".el")

    def test_scroll(self, executor, mock_ctrl):
        wf = {"nodes": [{"type": "action", "action": "Scroll", "selector": "window", "direction": "up", "amount": 500}]}
        result = executor.execute(wf)
        assert result["success"]
        mock_ctrl.scroll.assert_called_once_with("window", "up", 500)

    def test_select_option(self, executor, mock_ctrl):
        wf = {"nodes": [{"type": "action", "action": "SelectOption", "selector": "#sel", "value": "opt1"}]}
        result = executor.execute(wf)
        assert result["success"]
        mock_ctrl.select_option.assert_called_once_with("#sel", "opt1")

    def test_press_key(self, executor, mock_ctrl):
        wf = {"nodes": [{"type": "action", "action": "PressKey", "key": "Enter"}]}
        result = executor.execute(wf)
        assert result["success"]
        mock_ctrl.press_key.assert_called_once_with("body", "Enter")

    def test_clear(self, executor, mock_ctrl):
        wf = {"nodes": [{"type": "action", "action": "Clear", "selector": "#input"}]}
        result = executor.execute(wf)
        assert result["success"]
        mock_ctrl.clear.assert_called_once_with("#input")

    def test_focus(self, executor, mock_ctrl):
        wf = {"nodes": [{"type": "action", "action": "Focus", "selector": "#el"}]}
        result = executor.execute(wf)
        assert result["success"]
        mock_ctrl.focus.assert_called_once_with("#el")

    def test_go_back(self, executor, mock_ctrl):
        wf = {"nodes": [{"type": "action", "action": "GoBack"}]}
        result = executor.execute(wf)
        assert result["success"]
        mock_ctrl.go_back.assert_called_once()

    def test_go_forward(self, executor, mock_ctrl):
        wf = {"nodes": [{"type": "action", "action": "GoForward"}]}
        result = executor.execute(wf)
        assert result["success"]
        mock_ctrl.go_forward.assert_called_once()

    def test_reload(self, executor, mock_ctrl):
        wf = {"nodes": [{"type": "action", "action": "Reload"}]}
        result = executor.execute(wf)
        assert result["success"]
        mock_ctrl.reload.assert_called_once()

    def test_new_tab(self, executor, mock_ctrl):
        wf = {"nodes": [{"type": "action", "action": "NewTab", "url": "https://new.com"}]}
        result = executor.execute(wf)
        assert result["success"]
        mock_ctrl.new_tab.assert_called_once_with("https://new.com")

    def test_switch_tab(self, executor, mock_ctrl):
        wf = {"nodes": [{"type": "action", "action": "SwitchTab", "tabIndex": 2}]}
        result = executor.execute(wf)
        assert result["success"]
        mock_ctrl.switch_tab.assert_called_once_with(2)

    def test_close_tab(self, executor, mock_ctrl):
        wf = {"nodes": [{"type": "action", "action": "CloseTab", "tabIndex": 0}]}
        result = executor.execute(wf)
        assert result["success"]
        mock_ctrl.close_tab.assert_called_once_with(0)

    def test_handle_dialog(self, executor, mock_ctrl):
        wf = {"nodes": [{"type": "action", "action": "HandleDialog", "accept": False, "text": "ok"}]}
        result = executor.execute(wf)
        assert result["success"]
        mock_ctrl.handle_dialog.assert_called_once_with(accept=False, text="ok")

    def test_upload_file(self, executor, mock_ctrl):
        wf = {"nodes": [{"type": "action", "action": "UploadFile", "selector": "input", "filePath": "/tmp/f.txt"}]}
        result = executor.execute(wf)
        assert result["success"]
        mock_ctrl.upload_file.assert_called_once_with("input", "/tmp/f.txt")

    def test_extract_attr(self, executor, mock_ctrl):
        wf = {"nodes": [{"type": "action", "action": "GetAttribute", "selector": "a", "attrName": "href", "into": "$link"}]}
        result = executor.execute(wf)
        assert result["success"]
        assert result["variables"]["$link"] == "https://link.com"

    def test_extract_table(self, executor, mock_ctrl):
        wf = {"nodes": [{"type": "action", "action": "ExtractTable", "selector": "table", "into": "$data"}]}
        result = executor.execute(wf)
        assert result["success"]
        assert result["variables"]["$data"] == [["a", "b"], ["1", "2"]]

    def test_run_script(self, executor, mock_ctrl):
        wf = {"nodes": [{"type": "action", "action": "RunScript", "script": "return 1", "into": "$r"}]}
        result = executor.execute(wf)
        assert result["success"]
        assert result["variables"]["$r"] == "js_result"

    def test_fail(self, executor):
        wf = {"nodes": [{"type": "action", "action": "fail", "message": "boom"}]}
        result = executor.execute(wf)
        assert not result["success"]
        assert "boom" in result["error"]


# --- New Block tests ---

class TestNewBlocks:
    def test_switch_frame(self, executor, mock_ctrl):
        wf = {"nodes": [{"type": "action", "action": "SwitchFrame", "selector": "iframe#main"}]}
        result = executor.execute(wf)
        assert result["success"]
        mock_ctrl.switch_frame.assert_called_once_with("iframe#main")

    def test_wait_for_page(self, executor, mock_ctrl):
        wf = {"nodes": [{"type": "action", "action": "WaitForPage", "state": "networkidle", "timeout": 5000}]}
        result = executor.execute(wf)
        assert result["success"]
        mock_ctrl.wait_for_page.assert_called_once_with("networkidle", timeout=5000)

    def test_cookie_get(self, executor, mock_ctrl):
        wf = {"nodes": [{"type": "action", "action": "Cookie", "operation": "get", "into": "$cookies"}]}
        result = executor.execute(wf)
        assert result["success"]
        assert result["variables"]["$cookies"] == [{"name": "sid", "value": "abc"}]

    def test_cookie_set(self, executor, mock_ctrl):
        cookies = [{"name": "test", "value": "val", "url": "https://example.com"}]
        wf = {"nodes": [{"type": "action", "action": "Cookie", "operation": "set", "cookies": cookies}]}
        result = executor.execute(wf)
        assert result["success"]
        mock_ctrl.set_cookie.assert_called_once_with(cookies)

    def test_cookie_delete(self, executor, mock_ctrl):
        wf = {"nodes": [{"type": "action", "action": "Cookie", "operation": "delete", "name": "sid"}]}
        result = executor.execute(wf)
        assert result["success"]
        mock_ctrl.delete_cookie.assert_called_once_with("sid")

    def test_element_exists_true(self, executor, mock_ctrl):
        mock_ctrl.get_element_count.return_value = 1
        wf = {"nodes": [{"type": "action", "action": "ElementExists", "selector": "#el", "into": "$exists"}]}
        result = executor.execute(wf)
        assert result["success"]
        assert result["variables"]["$exists"] is True

    def test_element_exists_false(self, executor, mock_ctrl):
        mock_ctrl.get_element_count.return_value = 0
        wf = {"nodes": [{"type": "action", "action": "ElementExists", "selector": "#gone", "into": "$exists"}]}
        result = executor.execute(wf)
        assert result["success"]
        assert result["variables"]["$exists"] is False

    def test_handle_download(self, executor, mock_ctrl):
        mock_ctrl.handle_download.return_value = "/tmp/file.zip"
        wf = {"nodes": [{"type": "action", "action": "HandleDownload", "savePath": "/tmp/file.zip", "into": "$path"}]}
        result = executor.execute(wf)
        assert result["success"]
        mock_ctrl.handle_download.assert_called_once_with("/tmp/file.zip", timeout=30000)
        assert result["variables"]["$path"] == "/tmp/file.zip"

    def test_handle_download_custom_timeout(self, executor, mock_ctrl):
        mock_ctrl.handle_download.return_value = "/tmp/file.pdf"
        wf = {"nodes": [{"type": "action", "action": "HandleDownload", "savePath": "/tmp/file.pdf", "timeout": 5000}]}
        result = executor.execute(wf)
        assert result["success"]
        mock_ctrl.handle_download.assert_called_once_with("/tmp/file.pdf", timeout=5000)
        assert result["variables"]["$_result"] == "/tmp/file.pdf"

    def test_transform_sort(self, executor):
        wf = {"nodes": [
            {"type": "action", "action": "SetVariable", "variable": "$data", "value": [3, 1, 2]},
            {"type": "action", "action": "Transform", "source": "$data", "into": "$sorted", "operation": "sort"},
        ]}
        result = executor.execute(wf)
        assert result["success"]
        assert result["variables"]["$sorted"] == [1, 2, 3]

    def test_transform_unique(self, executor):
        wf = {"nodes": [
            {"type": "action", "action": "SetVariable", "variable": "$data", "value": [1, 2, 2, 3, 1]},
            {"type": "action", "action": "Transform", "source": "$data", "into": "$unique", "operation": "unique"},
        ]}
        result = executor.execute(wf)
        assert result["success"]
        assert result["variables"]["$unique"] == [1, 2, 3]

    def test_transform_flatten(self, executor):
        wf = {"nodes": [
            {"type": "action", "action": "SetVariable", "variable": "$data", "value": [[1, 2], [3], 4]},
            {"type": "action", "action": "Transform", "source": "$data", "into": "$flat", "operation": "flatten"},
        ]}
        result = executor.execute(wf)
        assert result["success"]
        assert result["variables"]["$flat"] == [1, 2, 3, 4]

    def test_stop(self, executor, mock_ctrl):
        wf = {"nodes": [
            {"type": "action", "action": "Stop"},
            {"type": "action", "action": "Click", "selector": "#never"},
        ]}
        result = executor.execute(wf)
        assert result["success"]
        mock_ctrl.click.assert_not_called()

    def test_execute_workflow(self, executor, mock_ctrl):
        sub_wf = {"nodes": [{"type": "action", "action": "SetVariable", "variable": "$sub_var", "value": "from_sub"}]}
        wf = {"nodes": [{"type": "action", "action": "ExecuteWorkflow", "workflow": sub_wf, "into": "$sub_result"}]}
        result = executor.execute(wf)
        assert result["success"]
        # Sub result should be stored
        sub_r = result["variables"]["$sub_result"]
        assert sub_r["success"]

    def test_wait_connections_noop(self, executor):
        wf = {"nodes": [{"type": "action", "action": "WaitConnections"}]}
        result = executor.execute(wf)
        assert result["success"]


# --- Control flow tests ---

class TestControlFlow:
    def test_condition_true(self, executor, mock_ctrl):
        mock_ctrl.get_element_count.return_value = 1
        wf = {"nodes": [{
            "type": "condition",
            "condition": 'exists("#el")',
            "children": [{"type": "action", "action": "SetVariable", "variable": "$branch", "value": "true"}],
            "elseChildren": [{"type": "action", "action": "SetVariable", "variable": "$branch", "value": "false"}],
        }]}
        result = executor.execute(wf)
        assert result["success"]
        assert result["variables"]["$branch"] == "true"

    def test_condition_false(self, executor, mock_ctrl):
        mock_ctrl.get_element_count.return_value = 0
        wf = {"nodes": [{
            "type": "condition",
            "condition": 'exists("#el")',
            "children": [{"type": "action", "action": "SetVariable", "variable": "$branch", "value": "true"}],
            "elseChildren": [{"type": "action", "action": "SetVariable", "variable": "$branch", "value": "false"}],
        }]}
        result = executor.execute(wf)
        assert result["success"]
        assert result["variables"]["$branch"] == "false"

    def test_loop_count(self, executor):
        wf = {"nodes": [{
            "type": "loop",
            "loopType": "count",
            "count": 3,
            "variable": "$i",
            "children": [{"type": "action", "action": "Log", "parts": ["iter"]}],
        }]}
        result = executor.execute(wf)
        assert result["success"]
        assert result["variables"]["$i"] == 2  # last iteration value

    def test_loop_breakpoint(self, executor):
        wf = {"nodes": [{
            "type": "loop",
            "loopType": "count",
            "count": 10,
            "variable": "$i",
            "children": [
                {"type": "action", "action": "SetVariable", "variable": "$last", "value": "placeholder"},
                {"type": "action", "action": "LoopBreakpoint"},
                {"type": "action", "action": "SetVariable", "variable": "$never", "value": True},
            ],
        }]}
        result = executor.execute(wf)
        assert result["success"]
        # Should break on first iteration at the breakpoint
        assert result["variables"]["$i"] == 0
        assert "$never" not in result["variables"]


# --- Error handling tests ---

class TestErrorHandling:
    def test_on_error_stop(self, executor, mock_ctrl):
        mock_ctrl.click.side_effect = RuntimeError("click failed")
        wf = {"nodes": [{"type": "action", "action": "Click", "selector": "#err", "settings": {"onError": "stop"}}]}
        result = executor.execute(wf)
        assert not result["success"]
        assert "click failed" in result["error"]

    def test_on_error_continue(self, executor, mock_ctrl):
        mock_ctrl.click.side_effect = RuntimeError("click failed")
        wf = {"nodes": [
            {"type": "action", "action": "Click", "selector": "#err", "settings": {"onError": "continue"}},
            {"type": "action", "action": "SetVariable", "variable": "$reached", "value": True},
        ]}
        result = executor.execute(wf)
        assert result["success"]
        assert result["variables"]["$reached"] is True

    def test_retry_then_succeed(self, executor, mock_ctrl):
        call_count = 0
        def click_eventually(sel):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("not yet")
        mock_ctrl.click.side_effect = click_eventually
        wf = {"nodes": [{"type": "action", "action": "Click", "selector": "#btn",
                         "settings": {"retryOnFail": True, "retryCount": 3, "retryInterval": 10}}]}
        result = executor.execute(wf)
        assert result["success"]
        assert call_count == 3

    def test_disabled_node_skipped(self, executor, mock_ctrl):
        wf = {"nodes": [{"type": "action", "action": "Click", "selector": "#btn", "settings": {"disabled": True}}]}
        result = executor.execute(wf)
        assert result["success"]
        mock_ctrl.click.assert_not_called()

    def test_variable_resolve(self, executor, mock_ctrl):
        wf = {"nodes": [
            {"type": "action", "action": "SetVariable", "variable": "$url", "value": "https://test.com"},
            {"type": "action", "action": "Navigate", "url": "$url"},
        ]}
        result = executor.execute(wf)
        assert result["success"]
        mock_ctrl.navigate.assert_called_once_with("https://test.com")

    def test_http_request_ssrf_blocked(self, executor):
        wf = {"nodes": [{"type": "action", "action": "HttpRequest", "url": "file:///etc/passwd"}]}
        result = executor.execute(wf)
        assert not result["success"]
        assert "scheme not allowed" in result["error"]


class TestProgressCallback:
    def test_executor_progress_callback(self, executor):
        """Executor should call progress_callback on each step."""
        progress_events = []

        def on_progress(event):
            progress_events.append(event)

        executor.progress_callback = on_progress
        workflow = {
            "name": "test",
            "nodes": [
                {"action": "Navigate", "url": "https://example.com"},
                {"action": "Screenshot", "filename": "test.png"},
            ]
        }
        executor.execute(workflow)
        assert len(progress_events) >= 2
        assert progress_events[0]["step"] == 0
        assert progress_events[0]["action"] == "open"
        assert progress_events[0]["status"] == "running"
        assert progress_events[1]["step"] == 1
        assert progress_events[1]["action"] == "screenshot"
