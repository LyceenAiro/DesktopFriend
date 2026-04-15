import json
from datetime import datetime
from os import listdir, makedirs, path, replace


class init_log:
    LEVEL_VALUES = {
        "DEBUG": 10,
        "INFO": 20,
        "WARN": 30,
        "ERROR": 40,
    }

    LEVEL_COLORS = {
        "DEBUG": "\033[1;90m",
        "INFO": "\033[1;36m",
        "WARN": "\033[1;33m",
        "ERROR": "\033[1;31m",
    }

    def __init__(self):
        self.log_dir = "log"
        self.log_file = path.join(self.log_dir, "timmer.log")
        self.max_file_size = 32 * 1024 * 1024
        self.level_name = "INFO"
        self._console_level_value = self.LEVEL_VALUES[self.level_name]
        if not path.exists(self.log_dir):
            makedirs(self.log_dir)
        self.pack_log()
        self.reload_from_debug_config()

    def _normalize_level_name(self, raw_level) -> str:
        if raw_level is None:
            return self.level_name
        if isinstance(raw_level, int):
            return self._legacy_level_to_name(raw_level)
        text = str(raw_level).strip().upper()
        if text == "WARNING":
            text = "WARN"
        if text not in self.LEVEL_VALUES:
            return self.level_name
        return text

    def _legacy_level_to_name(self, raw_level: int) -> str:
        # 兼容旧版 1~4 等级：1=INFO, 2=WARN, 3=ERROR, 4=静默文件写入（视为DEBUG）
        if raw_level <= 1:
            return "INFO"
        if raw_level == 2:
            return "WARN"
        if raw_level == 3:
            return "ERROR"
        return "DEBUG"

    def set_level(self, level) -> str:
        self.level_name = self._normalize_level_name(level)
        self._console_level_value = self.LEVEL_VALUES[self.level_name]
        return self.level_name

    def set_max_file_size_mb(self, size_mb) -> int:
        try:
            parsed = int(size_mb)
        except Exception:
            parsed = 32
        parsed = max(1, parsed)
        self.max_file_size = parsed * 1024 * 1024
        return parsed

    def reload_from_debug_config(self, config_path: str = "config/debug.cfg") -> None:
        data = {}
        if path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as file:
                    payload = json.load(file)
                if isinstance(payload, dict):
                    data = payload
            except Exception:
                data = {}

        self.set_level(data.get("log_level", "INFO"))
        self.set_max_file_size_mb(data.get("log_max_file_size_mb", 32))

    def pack_log(self):
        if not path.exists(self.log_file):
            return

        file_list = listdir(self.log_dir)
        date = datetime.now().strftime("%y_%m_%d_")
        prefix = f"timmer_{date}"

        suffixes = []
        for filename in file_list:
            if filename.startswith(prefix) and filename.endswith(".log"):
                suffix = filename[len(prefix):-4]
                if suffix.isdigit():
                    suffixes.append(int(suffix))

        next_suffix = 0 if not suffixes else max(suffixes) + 1
        new_filename = f"{prefix}{str(next_suffix).zfill(3)}.log"
        replace(self.log_file, path.join(self.log_dir, new_filename))

    def get_data(self) -> str:
        return datetime.now().strftime("[%y/%m/%d %H:%M:%S]")

    def _should_emit(self, level_name: str) -> bool:
        return self.LEVEL_VALUES[level_name] >= self._console_level_value

    def save_log(self, write_str: str):
        if path.exists(self.log_file) and path.getsize(self.log_file) > self.max_file_size:
            self.pack_log()
        with open(self.log_file, "a", encoding="utf-8") as file:
            file.write(write_str)

    def _log(self, level_name: str, message: str, tag: str | None = None):
        level_name = self._normalize_level_name(level_name)
        prefix = tag if tag else level_name
        line = f"{self.get_data()}[{prefix}]\t{message}"
        self.save_log(line + "\n")
        if self._should_emit(level_name):
            color = self.LEVEL_COLORS.get(level_name, "\033[1;36m")
            print(f"{color}{line}\033[0m")

    def DEBUG(self, string):
        self._log("DEBUG", str(string))

    def RUNNING(self, app, string):
        self._log("INFO", str(string), tag=str(app))

    def INFO(self, string):
        self._log("INFO", str(string))

    def WARN(self, string):
        self._log("WARN", str(string))

    def ERROR(self, string):
        self._log("ERROR", str(string))

    def WRITE(self, string, type="None"):
        if string == "" or string.startswith("&"):
            return
        self._log("DEBUG", str(string), tag=str(type))


_log = init_log()