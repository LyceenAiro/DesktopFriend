from os import path, makedirs, listdir, rename
from datetime import datetime

class init_log:
    def __init__(self):
        if not path.exists("log"):
            makedirs("log")
        self.max_file_size = 32 * 1024 * 1024 # 32MB
        self.level = 3
        self.pack_log()

    def pack_log(self):
        # 打包日志文件
        if path.exists(f"log/timmer.log"):
            # 日志文件命名
            file_list = listdir("log")
            date = datetime.now().strftime('%y_%m_%d_')
            prefix = f"timmer_{date}"

            suffixes = []
            for filename in file_list:
                if filename.startswith(prefix):
                    suffix = filename[len(prefix): -4]
                    suffixes.append(suffix)
            
            if not suffixes:
                new_suffix = "000"
            else:
                max_suffix = max(suffixes)
                new_suffix = str(int(max_suffix) + 1).zfill(len(max_suffix))
            new_filename = prefix + new_suffix + ".log"
            
            rename(f"log/timmer.log", f"log/{new_filename}")

    def save_log(self, write_str):
        if path.exists(f"log/timmer.log"):
            if path.getsize("log/timmer.log") > self.max_file_size:
                self.pack_log()
        with open(f"log/timmer.log", "a", encoding="utf-8") as file:
            file.write(write_str)
    
    def RUNNING(self, app, string):
        # 操作信息
        INFO_Colors = "\033[1;32m"
        date = datetime.now().strftime('[%y/%m/%d %H:%M:%S]')
        self.save_log(f"{date}[{app}]\t{string}\n")
        if self.level >= 1:
            print(f"{INFO_Colors}{date}[{app}]\033\t[0m{string}")
    
    def INFO(self, string):
        # 日志信息
        INFO_Colors = "\033[1;36m"
        date = datetime.now().strftime('[%y/%m/%d %H:%M:%S]')
        self.save_log(f"{date}[INFO]\t{string}\n")
        if self.level >= 1:
            print(f"{INFO_Colors}{date}[INFO]\033[0m\t{string}")

    def WARN(self, string):
        # 警告信息
        INFO_Colors = "\033[1;33m"
        date = datetime.now().strftime('[%y/%m/%d %H:%M:%S]')
        self.save_log(f"{date}[WARN]\t{string}\n")
        if self.level >= 2:
            print(f"{INFO_Colors}{date}[WARN]\033[0m\t{string}")

    def ERROR(self, string):
        # 错误信息
        INFO_Colors = "\033[1;31m"
        date = datetime.now().strftime('[%y/%m/%d %H:%M:%S]')
        self.save_log(f"{date}[ERROR]\t{string}\n")
        if self.level >= 3:
            print(f"{INFO_Colors}{date}[ERROR]\033[0m\t{string}")
    
    def WRITE(self, string, type="None"):
        # 静默写入
        INFO_Colors = "\033[1;36m"
        if string == "":
            return
        elif "&" == string[0]:
            return
        date = datetime.now().strftime('[%y/%m/%d %H:%M:%S]')
        self.save_log(f"{date}[{type}]\t{string}\n")
        if self.level >= 4:
            print(f"{INFO_Colors}{date}[{type}]\033[0m\t{string}")

_log = init_log()