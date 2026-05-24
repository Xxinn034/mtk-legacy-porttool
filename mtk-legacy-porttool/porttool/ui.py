# -*- coding: utf-8 -*-
import os, shutil, re
from pathlib import Path
from multiprocessing.dummy import DummyProcess
from tkinter import (
    ttk, scrolledtext, StringVar, BooleanVar, Canvas, Listbox,
    END, ACTIVE, Frame, Label, Entry, Button, Checkbutton,
    Radiobutton, OptionMenu, DISABLED, NORMAL, Toplevel,
)
from tkinter.filedialog import askopenfilename, askopenfilenames
from tkinterdnd2 import DND_FILES
from .configs import support_chipset, support_chipset_portstep
from .utils import portutils
from .twrp_port import port_twrp
from .bug_fix import fix_bugs, BUG_FIX_ITEMS
from .info_reader import get_boot_info, get_system_info, get_zip_info

# ========== 莫奈配色 ==========
BG = "#FEF7FF"
PRIMARY = "#6750A4"
ON_PRIMARY = "#FFFFFF"
ON_SURFACE = "#1C1B1F"
BTN_BG = "#E8DEF8"
BTN_FG = "#1C1B1F"
ENTRY_BG = "#FFFFFF"
ENTRY_FG = "#1C1B1F"
LISTBOX_BG = "#FFFFFF"
LISTBOX_FG = "#1C1B1F"
LOG_BG = "#FFFBFE"
LOG_FG = "#1C1B1F"

def apply_style():
    style = ttk.Style()
    style.theme_use("clam")
    style.configure(".", background=BG, foreground=ON_SURFACE)
    style.configure("TLabel", background=BG, foreground=ON_SURFACE)
    style.configure("TFrame", background=BG)
    style.configure("TLabelframe", background=BG, foreground=PRIMARY)
    style.configure("TLabelframe.Label", background=BG, foreground=PRIMARY)
    style.configure("TButton", background=BTN_BG, foreground=BTN_FG, borderwidth=1)
    style.map("TButton", background=[("active", "#D0BCFF")])
    style.configure("TEntry", fieldbackground=ENTRY_BG, foreground=ENTRY_FG)
    style.configure("TCheckbutton", background=BG, foreground=ON_SURFACE)
    style.map("TCheckbutton", background=[("active", BG)])
    style.configure("TRadiobutton", background=BG, foreground=ON_SURFACE)
    style.configure("TListbox", background=LISTBOX_BG, foreground=LISTBOX_FG, selectbackground=PRIMARY)
    style.configure("Vertical.TScrollbar", background=BTN_BG, troughcolor=BG)
    style.configure("TNotebook", background=BG, borderwidth=0)
    style.configure("TNotebook.Tab", background=BTN_BG, foreground=BTN_FG, padding=[10, 2])
    style.map("TNotebook.Tab", background=[("selected", PRIMARY)], foreground=[("selected", ON_PRIMARY)])

class LogLabel(scrolledtext.ScrolledText):
    def __init__(self, parent):
        super().__init__(parent, bg=LOG_BG, fg=LOG_FG, insertbackground=PRIMARY,
                         selectbackground=PRIMARY, selectforeground=ON_PRIMARY)
    def write(self, *vars, end='\n'):
        for i in vars:
            self.insert('end', i)
        self.insert('end', end)
        self.see('end')
    def flush(self): pass
    def print(self, *vars, end='\n'):
        print(vars, end=end, file=self)

# ---------- 拖放辅助 ----------
def _parse_drop_data(data):
    paths = []
    for match in re.finditer(r'\{([^}]*)\}|(\S+)', data):
        if match.group(1):
            paths.append(match.group(1))
        elif match.group(2):
            paths.append(match.group(2))
    return paths

def make_entry_droppable(entry_widget, var):
    entry_widget.drop_target_register(DND_FILES)
    entry_widget.dnd_bind('<<Drop>>', lambda e: var.set(_parse_drop_data(e.data)[0] if _parse_drop_data(e.data) else ""))

def make_listbox_droppable(listbox_widget):
    listbox_widget.drop_target_register(DND_FILES)
    listbox_widget.dnd_bind('<<Drop>>', lambda e: [
        listbox_widget.insert(END, path) for path in _parse_drop_data(e.data)
    ])

# ========== 设备信息面板 ==========
class InfoPanel(ttk.Frame):
    def __init__(self, parent, log_writer):
        super().__init__(parent)
        self.log = log_writer
        self._setup_ui()

    def _setup_ui(self):
        top = ttk.Frame(self)
        top.pack(side='top', fill='x', padx=10, pady=10)

        boot_frame = ttk.Labelframe(top, text="Boot 镜像信息")
        boot_frame.pack(side='left', fill='both', expand=True, padx=(0,5))

        self.boot_var = StringVar()
        row = ttk.Frame(boot_frame)
        e = ttk.Entry(row, textvariable=self.boot_var, width=25)
        e.pack(side='left', fill='x', expand=True, padx=5)
        make_entry_droppable(e, self.boot_var)
        ttk.Button(row, text="选择", command=lambda: self.boot_var.set(askopenfilename())).pack(side='left', padx=5)
        row.pack(fill='x', padx=5, pady=5)

        self.boot_text = scrolledtext.ScrolledText(boot_frame, height=12, bg=ENTRY_BG, fg=ENTRY_FG, wrap='word')
        self.boot_text.pack(fill='both', expand=True, padx=5, pady=5)
        ttk.Button(boot_frame, text="读取 boot 信息", command=self._read_boot).pack(pady=5)

        sys_frame = ttk.Labelframe(top, text="System 镜像信息")
        sys_frame.pack(side='left', fill='both', expand=True, padx=(5,0))

        self.sys_var = StringVar()
        row2 = ttk.Frame(sys_frame)
        e2 = ttk.Entry(row2, textvariable=self.sys_var, width=25)
        e2.pack(side='left', fill='x', expand=True, padx=5)
        make_entry_droppable(e2, self.sys_var)
        ttk.Button(row2, text="选择", command=lambda: self.sys_var.set(askopenfilename())).pack(side='left', padx=5)
        row2.pack(fill='x', padx=5, pady=5)

        self.sys_text = scrolledtext.ScrolledText(sys_frame, height=12, bg=ENTRY_BG, fg=ENTRY_FG, wrap='word')
        self.sys_text.pack(fill='both', expand=True, padx=5, pady=5)
        ttk.Button(sys_frame, text="读取 system 信息", command=self._read_sys).pack(pady=5)

        zip_frame = ttk.Labelframe(self, text="卡刷包 (zip) 信息")
        zip_frame.pack(side='top', fill='x', padx=10, pady=(10,10))

        self.zip_var = StringVar()
        row3 = ttk.Frame(zip_frame)
        e3 = ttk.Entry(row3, textvariable=self.zip_var, width=50)
        e3.pack(side='left', fill='x', expand=True, padx=5)
        make_entry_droppable(e3, self.zip_var)
        ttk.Button(row3, text="选择", command=lambda: self.zip_var.set(askopenfilename())).pack(side='left', padx=5)
        row3.pack(fill='x', padx=5, pady=5)

        self.zip_text = scrolledtext.ScrolledText(zip_frame, height=8, bg=ENTRY_BG, fg=ENTRY_FG, wrap='word')
        self.zip_text.pack(fill='both', expand=True, padx=5, pady=5)
        ttk.Button(zip_frame, text="读取卡刷包信息", command=self._read_zip).pack(pady=5)

    def _read_boot(self):
        path = self.boot_var.get().strip()
        if not path:
            self.log.write("【错误】请拖入或选择 boot.img\n")
            return
        self.log.write("正在解析 boot.img ...\n")
        info = get_boot_info(path, log_func=self.log.write)
        self.boot_text.delete('1.0', 'end')
        if info:
            mapping = {
                "cmdline": "内核命令行",
                "base": "基地址",
                "page_size": "页面大小",
                "name": "镜像名称",
                "kernel_version": "内核版本",
                "gcc_version": "GCC 版本"
            }
            for k, v in info.items():
                label = mapping.get(k, k)
                self.boot_text.insert('end', f"{label}: {v}\n")
        else:
            self.boot_text.insert('end', "解析失败，请检查日志")

    def _read_sys(self):
        path = self.sys_var.get().strip()
        if not path:
            self.log.write("【错误】请拖入或选择 system.img\n")
            return
        self.log.write("正在解析 system.img ...\n")
        info = get_system_info(path, log_func=self.log.write)
        self.sys_text.delete('1.0', 'end')
        if info:
            for k, v in info.items():
                self.sys_text.insert('end', f"{k}: {v}\n")
        else:
            self.sys_text.insert('end', "解析失败，请检查日志")

    def _read_zip(self):
        path = self.zip_var.get().strip()
        if not path:
            self.log.write("【错误】请拖入或选择卡刷包 zip\n")
            return
        self.log.write("正在解析卡刷包...\n")
        info = get_zip_info(path, log_func=self.log.write)
        self.zip_text.delete('1.0', 'end')
        if info:
            for k, v in info.items():
                self.zip_text.insert('end', f"{k}: {v}\n")
        else:
            self.zip_text.insert('end', "解析失败，请检查日志")

# ========== ROM 移植面板 ==========
class RomPortPanel(ttk.Frame):
    def __init__(self, parent, log_writer, on_process_start, on_process_end):
        super().__init__(parent)
        self.log = log_writer
        self.on_process_start = on_process_start
        self.on_process_end = on_process_end

        self.chipset_select = StringVar(value=support_chipset[0])
        self.item_vars = []
        self._setup_ui()
        self._load_port_items(self.chipset_select.get())

    def _setup_ui(self):
        chip_frame = ttk.Frame(self)
        ttk.Label(chip_frame, text="芯片方案：").pack(side='left', padx=5)
        self.chip_menu = OptionMenu(chip_frame, self.chipset_select, *support_chipset,
                                    command=lambda sel: self._load_port_items(sel))
        self.chip_menu.config(bg=BTN_BG, fg=BTN_FG)
        self.chip_menu.pack(side='left', fill='x', padx=5)
        chip_frame.pack(side='top', fill='x', pady=(10,5))

        actframe = ttk.Frame(self, relief='solid', borderwidth=1)
        self.actcanvas = Canvas(actframe, bg=BG, width=300, height=120, highlightthickness=0)
        scrollbar = ttk.Scrollbar(actframe, orient='vertical', command=self.actcanvas.yview)
        self.actcanvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.actcanvas.pack(side='left', fill='both', expand=True)
        actframe.pack(side='top', fill='both', expand=True, pady=(5,0))

        self.actcvframe = Frame(self.actcanvas, bg=BG)
        self.actcanvas.create_window((0,0), window=self.actcvframe, anchor='nw')
        self.actcvframe.bind("<Configure>", lambda e: self.actcanvas.configure(scrollregion=self.actcanvas.bbox("all")))

        bottom = ttk.Frame(self)
        bottom.pack(side='bottom', fill='both', expand=True, padx=10, pady=(10,5))

        base_frame = ttk.Frame(bottom)
        ttk.Label(base_frame, text="底包boot：").grid(row=0, column=0, padx=5, pady=2, sticky='e')
        self.baseboot_var = StringVar()
        e1 = ttk.Entry(base_frame, textvariable=self.baseboot_var, width=45)
        e1.grid(row=0, column=1, padx=5, pady=2)
        make_entry_droppable(e1, self.baseboot_var)
        ttk.Button(base_frame, text="选择", command=lambda: self.baseboot_var.set(askopenfilename())).grid(row=0, column=2, padx=5, pady=2)

        ttk.Label(base_frame, text="底包system：").grid(row=1, column=0, padx=5, pady=2, sticky='e')
        self.basesys_var = StringVar()
        e2 = ttk.Entry(base_frame, textvariable=self.basesys_var, width=45)
        e2.grid(row=1, column=1, padx=5, pady=2)
        make_entry_droppable(e2, self.basesys_var)
        ttk.Button(base_frame, text="选择", command=lambda: self.basesys_var.set(askopenfilename())).grid(row=1, column=2, padx=5, pady=2)

        if Path("base/system.img").exists():
            self.basesys_var.set(Path("base/system.img").absolute())
        if Path("base/boot.img").exists():
            self.baseboot_var.set(Path("base/boot.img").absolute())
        base_frame.pack(side='top', fill='x', pady=5)

        self.output_type = StringVar(value='zip')
        self.source_type = StringVar(value='zip')
        self.patch_magisk = BooleanVar(value=False)
        self.magisk_arch = StringVar(value='arm64')
        self.magisk_apk = StringVar(value="magisk.apk")

        out_frame = ttk.Frame(bottom)
        ttk.Label(out_frame, text="输出类型：").pack(side='left', padx=5)
        ttk.Radiobutton(out_frame, text="zip卡刷包", variable=self.output_type, value='zip',
                        command=self._update_source_state).pack(side='left', padx=5)
        ttk.Radiobutton(out_frame, text="img镜像", variable=self.output_type, value='img',
                        command=self._update_source_state).pack(side='left', padx=5)
        out_frame.pack(side='top', fill='x', pady=5)

        magisk_frame = ttk.Frame(bottom)
        self.magisk_check = ttk.Checkbutton(magisk_frame, text="修补 Magisk", variable=self.patch_magisk,
                                            command=self._toggle_magisk_options)
        self.magisk_check.pack(side='left', padx=5)

        self.arch_label = ttk.Label(magisk_frame, text="架构:")
        self.arch_menu = OptionMenu(magisk_frame, self.magisk_arch, "arm64", "arm", "x86", "x86_64")
        self.arch_menu.config(bg=BTN_BG, fg=BTN_FG)
        self.apk_label = ttk.Label(magisk_frame, text="APK:")
        self.apk_entry = ttk.Entry(magisk_frame, textvariable=self.magisk_apk, width=18)
        make_entry_droppable(self.apk_entry, self.magisk_apk)
        self.apk_btn = ttk.Button(magisk_frame, text="选择", command=lambda: self.magisk_apk.set(askopenfilename()))
        magisk_frame.pack(side='top', fill='x', pady=5)
        self._toggle_magisk_options()

        source_frame = ttk.Frame(bottom)
        ttk.Label(source_frame, text="移植源类型：").pack(side='left', padx=5)
        self.zip_radio = ttk.Radiobutton(source_frame, text="zip卡刷包", variable=self.source_type, value='zip',
                                         command=self._update_list_label)
        self.zip_radio.pack(side='left', padx=5)
        self.img_radio = ttk.Radiobutton(source_frame, text="单独img镜像", variable=self.source_type, value='img',
                                         command=self._update_list_label)
        self.img_radio.pack(side='left', padx=5)
        source_frame.pack(side='top', fill='x', pady=5)

        list_outer = ttk.Frame(bottom)
        self.list_label = ttk.Label(list_outer, text="已添加的包：")
        self.list_label.pack(anchor='w')
        self.port_listbox = Listbox(list_outer, height=5, bg=LISTBOX_BG, fg=LISTBOX_FG,
                                    selectbackground=PRIMARY, selectforeground=ON_PRIMARY)
        self.port_listbox.pack(side='top', fill='both', expand=True)
        make_listbox_droppable(self.port_listbox)
        btn_row = ttk.Frame(list_outer)
        ttk.Button(btn_row, text="添加包", command=self._add_files).pack(side='left', padx=2)
        ttk.Button(btn_row, text="移除选中", command=lambda: self.port_listbox.delete(ACTIVE)).pack(side='left', padx=2)
        ttk.Button(btn_row, text="清空", command=lambda: self.port_listbox.delete(0, END)).pack(side='left', padx=2)
        btn_row.pack(side='top', fill='x', pady=(5,0))
        list_outer.pack(side='top', fill='both', expand=True, pady=10)

        ttk.Button(bottom, text="开始移植ROM", command=self._start_port).pack(side='top', pady=10)
        self._update_source_state()

    def _load_port_items(self, select):
        for w in self.actcvframe.winfo_children():
            w.destroy()
        self.item_vars.clear()
        item_dict = support_chipset_portstep[select]['flags']
        for key, value in item_dict.items():
            var = BooleanVar(value=value)
            self.item_vars.append((key, var))
            cb = Checkbutton(self.actcvframe, text=key, variable=var,
                             bg=BG, fg=ON_SURFACE, selectcolor=BG,
                             activebackground=BG, indicatoron=True,
                             anchor='w', padx=20)
            cb.pack(side='top', fill='x', pady=1)
        self.actcanvas.configure(scrollregion=self.actcanvas.bbox("all"))

    def _update_source_state(self):
        if self.output_type.get() == 'zip':
            self.source_type.set('zip')
            self.zip_radio.config(state=DISABLED)
            self.img_radio.config(state=DISABLED)
        else:
            self.zip_radio.config(state=NORMAL)
            self.img_radio.config(state=NORMAL)
        self._update_list_label()

    def _update_list_label(self):
        if self.source_type.get() == 'zip':
            self.list_label.config(text="已添加的包(zip)：")
        else:
            self.list_label.config(text="已添加的包(boot | system)：")

    def _add_files(self):
        if self.source_type.get() == 'zip':
            files = askopenfilenames(title="选择移植包(zip)")
            for f in files:
                self.port_listbox.insert(END, f)
        else:
            boot = askopenfilename(title="选择 boot.img")
            if boot:
                sys = askopenfilename(title="选择 system.img")
                if sys:
                    self.port_listbox.insert(END, f"{boot} | {sys}")

    def _toggle_magisk_options(self):
        if self.patch_magisk.get():
            self.arch_label.pack(side='left', padx=5)
            self.arch_menu.pack(side='left', padx=5)
            self.apk_label.pack(side='left', padx=5)
            self.apk_entry.pack(side='left', padx=5)
            self.apk_btn.pack(side='left', padx=5)
        else:
            for w in [self.arch_label, self.arch_menu, self.apk_label, self.apk_entry, self.apk_btn]:
                w.pack_forget()

    def _start_port(self):
        baseboot = self.baseboot_var.get()
        basesys = self.basesys_var.get()
        raw_list = list(self.port_listbox.get(0, END))
        source_type = self.source_type.get()
        output_type = self.output_type.get()

        if not baseboot or not basesys:
            self.log.write("【错误】请选择底包 boot 和 system\n")
            return
        if not raw_list:
            self.log.write("【错误】请添加至少一个移植包\n")
            return

        if output_type == 'img' and source_type == 'img':
            port_list = []
            for item in raw_list:
                if ' | ' in item:
                    b, s = item.split(' | ')
                    port_list.append((b.strip(), s.strip()))
        else:
            port_list = raw_list

        newdict = support_chipset_portstep[self.chipset_select.get()]
        for key, var in self.item_vars:
            newdict[key] = var.get()
        newdict['patch_magisk'] = self.patch_magisk.get()
        newdict['magisk_apk'] = self.magisk_apk.get()
        newdict['target_arch'] = self.magisk_arch.get()
        genimg = output_type == 'img'

        self.log.write(f"【一键移植ROM】开始，共 {len(port_list)} 个包\n")
        self.on_process_start()

        def run():
            try:
                if os.path.exists("out"):
                    shutil.rmtree("out", ignore_errors=True)
                for idx, pkg in enumerate(port_list, 1):
                    self.log.write(f"\n{'='*40}\n[{idx}/{len(port_list)}] 处理...\n")
                    portutils(newdict, baseboot, basesys, pkg, source_type, genimg, self.log).start()
                    # 确定输出目录名
                    if source_type == 'zip' or output_type == 'zip':
                        base_name = Path(pkg).stem if isinstance(pkg, str) else f"out_{idx}"
                        target_dir = base_name
                        counter = 1
                        while os.path.exists(target_dir):
                            target_dir = f"{base_name}_{counter}"
                            counter += 1
                    else:
                        # 非 zip 源 (img 源)：使用 boot.img 所在文件夹名
                        if isinstance(pkg, tuple) and len(pkg) == 2:
                            boot_path = pkg[0]
                            folder_name = Path(boot_path).parent.name
                            target_dir = folder_name if folder_name else f"out_{idx}"
                        else:
                            target_dir = f"out_{idx}"
                        # 如果已存在同名文件夹，添加数字后缀
                        if os.path.exists(target_dir):
                            counter = 1
                            base_target = target_dir
                            while os.path.exists(f"{base_target}_{counter}"):
                                counter += 1
                            target_dir = f"{base_target}_{counter}"
                    if os.path.exists("out"):
                        os.rename("out", target_dir)
                        self.log.write(f"输出保存到 {target_dir}/\n")
                self.log.write("\n【一键移植ROM】完成！\n")
            except Exception as e:
                self.log.write(f"【异常】{e}\n")
            finally:
                self.on_process_end()

        DummyProcess(target=run).start()

# ========== Bug 修复面板 ==========
class BugFixPanel(ttk.Frame):
    def __init__(self, parent, log_writer, on_process_start, on_process_end):
        super().__init__(parent)
        self.log = log_writer
        self.on_process_start = on_process_start
        self.on_process_end = on_process_end
        self.fix_button = None
        self._setup_ui()

    def _setup_ui(self):
        row1 = ttk.Frame(self)
        ttk.Label(row1, text="原系统（system/zip）：").pack(side='left', padx=5)
        self.base_sys_var = StringVar()
        e1 = ttk.Entry(row1, textvariable=self.base_sys_var, width=50)
        e1.pack(side='left', padx=5)
        make_entry_droppable(e1, self.base_sys_var)
        ttk.Button(row1, text="选择", command=lambda: self.base_sys_var.set(askopenfilename(
            filetypes=[("System 文件", "*.img;*.zip"), ("所有文件", "*.*")]
        ))).pack(side='left', padx=5)
        row1.pack(side='top', fill='x', padx=10, pady=10)

        row2 = ttk.Frame(self)
        ttk.Label(row2, text="待修复（system/zip）：").pack(side='left', padx=5)
        self.port_rom_var = StringVar()
        e2 = ttk.Entry(row2, textvariable=self.port_rom_var, width=50)
        e2.pack(side='left', padx=5)
        make_entry_droppable(e2, self.port_rom_var)
        ttk.Button(row2, text="选择", command=lambda: self.port_rom_var.set(askopenfilename(
            filetypes=[("ROM 文件", "*.img;*.zip"), ("所有文件", "*.*")]
        ))).pack(side='left', padx=5)
        row2.pack(side='top', fill='x', padx=10, pady=10)

        check_frame = ttk.Frame(self)
        self.check_vars = {}
        for key, item in BUG_FIX_ITEMS.items():
            var = BooleanVar(value=False)
            self.check_vars[key] = var
            cb = Checkbutton(check_frame, text=f"{item['name']} - {item['description']}",
                             variable=var, bg=BG, fg=ON_SURFACE, selectcolor=BG,
                             activebackground=BG, indicatoron=True, anchor='w', padx=20)
            cb.pack(anchor='w', fill='x', padx=5, pady=2)
        check_frame.pack(side='top', fill='both', expand=True, padx=10, pady=10)

        self.fix_button = ttk.Button(self, text="开始修复", command=self._start_fix)
        self.fix_button.pack(side='bottom', pady=10)

    def _start_fix(self):
        base_sys = self.base_sys_var.get()
        port_rom = self.port_rom_var.get()
        if not base_sys or not port_rom:
            self.log.write("【错误】请选择原系统文件和待修复 ROM\n")
            return
        selected = [k for k, v in self.check_vars.items() if v.get()]
        if not selected:
            self.log.write("【错误】请至少勾选一个修复项\n")
            return
        self.fix_button.config(state='disabled')
        self.log.write("【初步修复bug】开始…\n")
        self.on_process_start()
        def run():
            try:
                success = fix_bugs(base_sys, port_rom, selected, self.log)
                if success:
                    self.log.write("【初步修复bug】完成！\n")
                else:
                    self.log.write("【初步修复bug】失败，请检查日志\n")
            except Exception as e:
                self.log.write(f"【异常】{e}\n")
            finally:
                self.fix_button.config(state='normal')
                self.on_process_end()
        DummyProcess(target=run).start()

# ========== TWRP 移植面板 ==========
class TwrpPortPanel(ttk.Frame):
    def __init__(self, parent, log_writer, on_process_start, on_process_end):
        super().__init__(parent)
        self.log = log_writer
        self.on_process_start = on_process_start
        self.on_process_end = on_process_end
        self._setup_ui()

    def _setup_ui(self):
        row1 = ttk.Frame(self)
        ttk.Label(row1, text="原厂 recovery.img：").pack(side='left', padx=5)
        self.official_var = StringVar()
        e1 = ttk.Entry(row1, textvariable=self.official_var, width=50)
        e1.pack(side='left', padx=5)
        make_entry_droppable(e1, self.official_var)
        ttk.Button(row1, text="选择", command=lambda: self.official_var.set(askopenfilename())).pack(side='left', padx=5)
        row1.pack(side='top', fill='x', padx=10, pady=10)

        list_frame = ttk.Frame(self)
        ttk.Label(list_frame, text="待移植的 recovery 列表：").pack(anchor='w', padx=5)
        self.task_listbox = Listbox(list_frame, height=8, bg=LISTBOX_BG, fg=LISTBOX_FG,
                                    selectbackground=PRIMARY, selectforeground=ON_PRIMARY)
        self.task_listbox.pack(side='top', fill='both', expand=True, padx=5, pady=5)
        make_listbox_droppable(self.task_listbox)
        list_frame.pack(side='top', fill='both', expand=True, padx=10, pady=5)

        btn_frame = ttk.Frame(self)
        ttk.Button(btn_frame, text="添加 recovery", command=self._add_task).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="移除选中", command=lambda: self.task_listbox.delete(ACTIVE)).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="清空", command=lambda: self.task_listbox.delete(0, END)).pack(side='left', padx=2)
        btn_frame.pack(side='top', fill='x', padx=10, pady=5)

        ttk.Button(self, text="开始移植TWRP", command=self._start_port).pack(side='bottom', pady=10)

    def _add_task(self):
        files = askopenfilenames(title="选择要移植的 recovery.img（可多选）")
        for f in files:
            self.task_listbox.insert(END, f)

    def _start_port(self):
        official = self.official_var.get()
        if not official or not os.path.isfile(official):
            self.log.write("【错误】请选择原厂 recovery.img\n")
            return
        tasks = list(self.task_listbox.get(0, END))
        if not tasks:
            self.log.write("【错误】任务列表为空\n")
            return
        self.log.write("【一键移植TWRP】开始…\n")
        self.on_process_start()
        def run():
            total = len(tasks)
            for idx, rec in enumerate(tasks, 1):
                self.log.write(f"\n--- [{idx}/{total}] 处理中 ---\n")
                port_name = Path(rec).stem
                target_dir = port_name
                counter = 1
                while os.path.exists(target_dir):
                    target_dir = f"{port_name}_{counter}"
                    counter += 1
                os.makedirs(target_dir, exist_ok=True)
                try:
                    success = port_twrp(official, rec, self.log, output_dir=target_dir)
                    if success:
                        self.log.write(f"完成，输出目录：{os.path.abspath(target_dir)}\n")
                    else:
                        self.log.write("失败\n")
                except Exception as e:
                    self.log.write(f"异常：{e}\n")
            self.log.write("【一键移植TWRP】全部完成！\n")
            self.on_process_end()
        DummyProcess(target=run).start()

# ========== 主程序 ==========
class MainApp:
    def __init__(self, root):
        self.root = root
        root.title("MTK Legacy Port Tool - 联发科低端设备移植工具 by Xxinn")
        root.geometry("950x680")               # 缩小默认尺寸
        root.configure(bg=BG)
        apply_style()

        main_frame = ttk.Frame(root)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(side='left', fill='both', expand=True)

        log_container = ttk.Frame(main_frame)
        ttk.Label(log_container, text="日志输出：", font=("微软雅黑", 10, "bold")).pack(anchor='w', pady=(0,5))
        self.log = LogLabel(log_container)
        self.log.pack(fill='both', expand=True)
        log_container.pack(side='right', fill='both', expand=True, padx=(10,0))

        self.info_panel = InfoPanel(self.notebook, self.log)
        self.rom_panel = RomPortPanel(self.notebook, self.log, self._on_start, self._on_end)
        self.bugfix_panel = BugFixPanel(self.notebook, self.log, self._on_start, self._on_end)
        self.twrp_panel = TwrpPortPanel(self.notebook, self.log, self._on_start, self._on_end)

        self.notebook.add(self.info_panel, text="设备信息")
        self.notebook.add(self.rom_panel, text="一键移植ROM")
        self.notebook.add(self.bugfix_panel, text="初步修复bug")
        self.notebook.add(self.twrp_panel, text="一键移植TWRP")

    def _on_start(self):
        pass
    def _on_end(self):
        pass