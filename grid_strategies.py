# -*- coding: utf-8 -*-
import abc
import io
import tempfile
from io import StringIO
from typing import TYPE_CHECKING, Dict, List, Optional

import pandas as pd
import pywinauto.keyboard
import pywinauto
import pywinauto.clipboard
import time
from jqktrader.log import logger
from jqktrader.utils.captcha import captcha_recognize
from jqktrader.utils.win_gui import ShowWindow, win32defines

if TYPE_CHECKING:
    # pylint: disable=unused-import
    from jqktrader import clienttrader


class IGridStrategy(abc.ABC):
    @abc.abstractmethod
    def get(self, control_id: int) -> List[Dict]:
        """
        获取 gird 数据并格式化返回

        :param control_id: grid 的 control id
        :return: grid 数据
        """
        pass

    @abc.abstractmethod
    def set_trader(self, trader: "clienttrader.IClientTrader"):
        pass


class BaseStrategy(IGridStrategy):
    def __init__(self):
        self._trader = None

    def set_trader(self, trader: "clienttrader.IClientTrader"):
        self._trader = trader

    @abc.abstractmethod
    def get(self, control_id: int) -> List[Dict]:
        """
        :param control_id: grid 的 control id
        :return: grid 数据
        """
        pass

    def _get_grid(self, control_id: int):
        grid = self._trader.main.child_window(
            control_id=control_id, class_name="CVirtualGridCtrl"
        )
        return grid

    def _set_foreground(self, grid=None):
        try:
            if grid is None:
                grid = self._trader.main
            if grid.has_style(win32defines.WS_MINIMIZE):  # if minimized
                ShowWindow(grid.wrapper_object(), 9)  # restore window state
            else:
                grid.wrapper_object().set_focus()
                # SetForegroundWindow(grid.wrapper_object())  # bring to front
        except:
            pass


class Copy(BaseStrategy):
    """
    通过复制 grid 内容到剪切板再读取来获取 grid 内容
    """

    _need_captcha_reg = True

    def get(self, control_id: int) -> List[Dict]:
        grid = self._get_grid(control_id)

        self._set_foreground(grid)

        # 全选复制
        grid.type_keys("^A^C", set_foreground=False)

        # 等待剪贴板更新
        time.sleep(0.2)

        content = self._get_clipboard_data()

        return self._format_grid_data(content)

    def _format_grid_data(self, data: str) -> List[Dict]:
        try:
            df = pd.read_csv(
                io.StringIO(data),
                delimiter="\t",
                dtype=self._trader.config.GRID_DTYPE,
                na_filter=False,
            )

            return df.to_dict("records")

        except Exception as e:
            logger.exception(e)
            Copy._need_captcha_reg = True
            return []

    def _get_clipboard_data(self) -> str:
        dlg = self._trader.app.top_window()

        logger.info("开始读取剪贴板")

        # 验证码处理
        if Copy._need_captcha_reg:

            captcha_window = dlg.window(
                class_name="Static",
                title_re="验证码"
            )

            # 检测验证码窗口
            if captcha_window.exists(timeout=3):

                logger.info("检测到验证码窗口")

                img_ctrl = dlg.window(
                    control_id=0x965,
                    class_name="Static"
                )

                edit_ctrl = dlg.window(
                    control_id=0x964,
                    class_name="Edit"
                )

                confirm_btn = dlg.window(title="确定")

                success = False

                # 最多尝试5次
                for i in range(5):

                    try:
                        logger.info(f"验证码识别第 {i + 1} 次")

                        # 等待验证码渲染
                        time.sleep(0.3)

                        # 临时文件
                        file_path = f"tmp_captcha_{i}.png"

                        # 截图验证码
                        img_ctrl.capture_as_image().save(file_path)

                        # OCR识别
                        captcha_num = captcha_recognize(file_path)

                        logger.info(
                            f"captcha result --> {captcha_num}"
                        )

                        # 删除临时文件
                        try:
                            os.remove(file_path)
                        except Exception:
                            pass

                        # 校验验证码
                        if (
                            len(captcha_num) != 4
                            or not captcha_num.isdigit()
                        ):

                            logger.warning("验证码格式错误")

                            # 刷新验证码
                            img_ctrl.click_input()

                            continue

                        # 输入验证码
                        edit_ctrl.set_focus()

                        # 清空输入框
                        edit_ctrl.set_edit_text("")

                        time.sleep(0.1)

                        # 输入验证码
                        edit_ctrl.set_edit_text(captcha_num)

                        time.sleep(0.1)

                        # 点击确定
                        confirm_btn.click_input()

                        # 等待验证结果
                        time.sleep(0.8)

                        # 验证码窗口消失 => 成功
                        if not captcha_window.exists(timeout=1):

                            logger.info("验证码识别成功")

                            success = True

                            break

                        logger.warning("验证码错误，重新尝试")

                        # 刷新验证码
                        img_ctrl.click_input()

                    except Exception as e:

                        logger.exception(e)

                        # 尝试刷新验证码
                        try:
                            img_ctrl.click_input()
                        except Exception:
                            pass

                # 连续失败
                if not success:

                    logger.error("验证码连续识别失败")

                    try:
                        dlg.Button2.click()
                    except Exception:
                        pass

                    raise Exception("验证码识别失败")

            else:
                # 当前无需验证码
                Copy._need_captcha_reg = False

        # 剪贴板读取
        for i in range(10):

            try:
                data = pywinauto.clipboard.GetData()

                # 判断数据有效
                if data and len(data.strip()) > 0:

                    logger.info("剪贴板读取成功")

                    return data

            except Exception as e:

                logger.warning(
                    f"读取剪贴板失败，第 {i + 1} 次重试: {e}"
                )

            time.sleep(0.2)

        raise Exception("读取剪贴板失败")

class Copy_bak(BaseStrategy):
    """
    通过复制 grid 内容到剪切板再读取来获取 grid 内容
    """

    _need_captcha_reg = True

    def get(self, control_id: int) -> List[Dict]:
        grid = self._get_grid(control_id)
        self._set_foreground(grid)
        grid.type_keys("^A^C", set_foreground=False)
        content = self._get_clipboard_data()
        return self._format_grid_data(content)

    def _format_grid_data(self, data: str) -> List[Dict]:
        try:
            df = pd.read_csv(
                io.StringIO(data),
                delimiter="\t",
                dtype=self._trader.config.GRID_DTYPE,
                na_filter=False,
            )
            return df.to_dict("records")
        except:
            Copy._need_captcha_reg = True

    def _get_clipboard_data(self) -> str:
        print("start 1")
        print(self._trader.app.top_window().print_control_identifiers())
        if Copy._need_captcha_reg:
            if (
                    self._trader.app.top_window().window(class_name="Static", title_re="验证码").exists(timeout=3)
            ):
                file_path = "tmp.png"
                count = 5
                found = False
                print("start 2")
                while count > 0:
                    self._trader.app.top_window().window(
                        control_id=0x965, class_name="Static"
                    ).capture_as_image().save(
                        file_path
                    )  # 保存验证码

                    captcha_num = captcha_recognize(file_path).strip()  # 识别验证码
                    captcha_num = "".join(captcha_num.split())
                    logger.info("captcha result-->" + captcha_num)
                    if len(captcha_num) == 4:
                        self._trader.app.top_window().window(
                            control_id=0x964, class_name="Edit"
                        ).set_focus()

                        pywinauto.keyboard.SendKeys("{BKSP}{BKSP}{BKSP}{BKSP}")

                        pywinauto.keyboard.SendKeys(captcha_num)

                        self._trader.app.top_window().set_focus()
                        pywinauto.keyboard.SendKeys("{ENTER}")  # 模拟发送enter，点击确定

                        if (self._trader.app.top_window().window(class_name="Static", title_re="验证码").exists(timeout=1)):
                            logger.info("验证码识别错误")
                        else:
                            found = True
                            break
                        # try:
                        #     logger.info(
                        #         self._trader.app.top_window()
                        #             .window(control_id=0x966, class_name="Static")
                        #             .window_text()
                        #     )
                        # except Exception as ex:  # 窗体消失
                        #     logger.exception(ex)
                        #     found = True
                        #     break
                    count -= 1
                    self._trader.wait(0.1)
                    self._trader.app.top_window().window(
                        control_id=0x965, class_name="Static"
                    ).click()
                if not found:
                    print("start 3")
                    self._trader.app.top_window().Button2.click()  # 点击取消
            else:
                Copy._need_captcha_reg = False
        count = 5
        while count > 0:
            try:
                return pywinauto.clipboard.GetData()
            # pylint: disable=broad-except
            except Exception as e:
                count -= 1
                logger.exception("%s, retry ......", e)


class WMCopy(Copy):
    """
    通过复制 grid 内容到剪切板再读取来获取 grid 内容
    """

    def get(self, control_id: int) -> List[Dict]:
        grid = self._get_grid(control_id)
        grid.post_message(win32defines.WM_COMMAND, 0xE122, 0)
        self._trader.wait(0.1)
        content = self._get_clipboard_data()
        return self._format_grid_data(content)


class Xls(BaseStrategy):
    """
    通过将 Grid 另存为 xls 文件再读取的方式获取 grid 内容
    """

    def __init__(self, tmp_folder: Optional[str] = None):
        """
        :param tmp_folder: 用于保持临时文件的文件夹
        """
        super().__init__()
        self.tmp_folder = tmp_folder

    def get(self, control_id: int) -> List[Dict]:
        grid = self._get_grid(control_id)

        # ctrl+s 保存 grid 内容为 xls 文件
        self._set_foreground(grid)  # setFocus buggy, instead of SetForegroundWindow
        grid.type_keys("^s", set_foreground=False)
        count = 10
        while count > 0:
            if self._trader.is_exist_pop_dialog():
                break
            self._trader.wait(0.2)
            count -= 1

        temp_path = tempfile.mktemp(suffix=".xls", dir=self.tmp_folder)
        self._set_foreground(self._trader.app.top_window())

        # alt+s保存，alt+y替换已存在的文件
        self._trader.app.top_window().Edit1.set_edit_text(temp_path)
        self._trader.wait(0.1)
        self._trader.app.top_window().type_keys("%{s}%{y}", set_foreground=False)
        # Wait until file save complete otherwise pandas can not find file
        self._trader.wait(0.2)
        if self._trader.is_exist_pop_dialog():
            self._trader.app.top_window().Button2.click()
            self._trader.wait(0.2)

        return self._format_grid_data(temp_path)

    def _format_grid_data(self, data: str) -> List[Dict]:
        with open(data, encoding="gbk", errors="replace") as f:
            content = f.read()

        df = pd.read_csv(
            StringIO(content),
            delimiter="\t",
            dtype=self._trader.config.GRID_DTYPE,
            na_filter=False,
        )
        return df.to_dict("records")
