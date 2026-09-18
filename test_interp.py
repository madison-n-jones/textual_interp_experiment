from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Input, TextArea, Button, Select, Log, DirectoryTree, Label, Checkbox, Placeholder, ProgressBar, Static
from textual.containers import HorizontalGroup, Horizontal, VerticalGroup, Vertical, VerticalScroll
from textual.binding import Binding
from textual.theme import Theme
from textual.reactive import reactive
from textual import work
from textual.screen import ModalScreen
import os,time
from pathlib import Path
from typing import Iterable
import cstorm_utils.interp.stacks as cu

#TODO Reconsider the color of buttons. Its very bright on the right side of the screen
#TODO This can almost certianly be handled with input validators
class FileValidator:
    """
    Base container that monitors nested Input widgets for file path existence
    on blur and submit events.
    """
    new_file = False
    ready = reactive(None)

    def watch_ready(self,ready):
        if hasattr(self.parent,"paths_ready"):
            self.parent.paths_ready[self.id] = ready
            self.parent.mutate_reactive(self.parent.__class__.paths_ready)

    #def on_input_blurred(self, event: Input.Blurred) -> None:
    #    self.check_file_path(event.input)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.check_file_path(event.input)

    def check_file_path(self, input_widget: Input) -> bool:
        if self.new_file: return
        raw_path = input_widget.value.strip()
        if not getattr(self,"_original_tooltip",False): self._original_tooltip = getattr(input_widget,"tooltip",None)
        # Ignore empty values if desired
        if not raw_path:
            input_widget.remove_class("-invalid-file")
            self.ready = None
            return None

        path = Path(raw_path).expanduser().resolve()
        
        if path.exists():
            input_widget.remove_class("-invalid-file")
            input_widget.tooltip = self._original_tooltip
            self.ready = True
            return True
        else:
            input_widget.add_class("-invalid-file")
            #input_widget.tooltip = f"File Not Found{'\n' + self._original_tooltip if self._original_tooltip is not None else ''}" ## syntax error in Python versions 3.11 and lower
            input_widget.tooltip = f"File Not Found{self._original_tooltip if self._original_tooltip is not None else ''}" ## switch to this line unless using 3.12+
            self.ready = False
            return False

class FilePickerRow(Horizontal,FileValidator):
    """A reusable, self-contained row with an etched label, an input, and a browse button."""

    # Custom message emitted when this specific row's button is clicked
    """ class Selected(Message):
        def __init__(self, row: "FilePickerRow") -> None:
            super().__init__()
            self.row = row """

    def __init__(
        self,
        label_text: str,
        placeholder: str = "/path/to/file",
        initial_value: str = "",
        tooltip: str = "",
        input_field_id: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.label_text = label_text
        self.placeholder = placeholder
        self.initial_value = initial_value
        self.tooltip = tooltip
        if input_field_id is not None:
            self.input_field_id = input_field_id
        else:
            self.input_field_id = f"{self.id}_path"

    def compose(self) -> ComposeResult:
        yield Label(self.label_text)
        yield Input(value=self.initial_value, placeholder=self.placeholder, tooltip = self.tooltip, id = f"{self.id}_path")
        yield ClearButton(f"#{self.id}_path")
        yield SelectFile(input_field_id=self.input_field_id)
        
class FilteredDirectoryTree(DirectoryTree):
    """ Probably unnecessary method to ignore hidden files/directories from tree."""
    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [path for path in paths if not path.name.startswith(".") or path == ".."]

class FilePickerModal(ModalScreen[Path]):
    """A pop-up window containing a directory browser.
        Displaying CWD only.
    """
    BINDINGS = [("q", "close_modal", "Quit"),
                ("u", "up_dir", "Go up one dir")]

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-container"):
            yield Label("Select a File ('u': Up one dir  'q': close)")
            path = os.getcwd()
            yield Input(value=path,id = "dir_tree_path") #TODO Add a button horizontal to this to go up one dir
            dir_tree = FilteredDirectoryTree(path,id = "dir_tree")
            yield dir_tree
            dir_tree.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        path = Path(event.value.strip()).expanduser().resolve()
        if path.exists():
            self.query_one("#dir_tree_path").remove_class("-invalid-file")
            self.query_one("#dir_tree").path = path
        else:
            self.query_one("#dir_tree_path").add_class("-invalid-file")

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Dismiss the modal screen and return the chosen file path."""
        event.stop()
        self.dismiss(event.path)
    
    def action_close_modal(self) -> None:
        self.app.pop_screen()

    def action_up_dir(self) -> None:
        dir_tree = self.query_one("#dir_tree")
        path = Path(dir_tree.path).parent
        if path != dir_tree.path:
            dir_tree.path = path
            self.query_one("#dir_tree_path").value = str(path)


class SelectFile(Button,FileValidator): 
    """ Creating widget to select files from directory tree."""
    def __init__(
        self,
        input_field_id: str,
        label: str = "\U0001F4C2",
        id: str | None = None
        ) -> None:

        super().__init__(
            label=label,
            id=id,
            variant="primary"
        )

        self.input_field_id = input_field_id

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.app.push_screen(FilePickerModal(), callback=self.handle_file_chosen)

    def handle_file_chosen(self, chosen_file: Path | None) -> None:
        if chosen_file:
            chosen_file_path = self.screen.query_one(f"#{self.input_field_id}", Input)
            chosen_file_path.value = str(chosen_file)
            chosen_file_path.post_message(Input.Submitted(chosen_file_path, chosen_file_path.value))


class ClearButton(Button):
    """A statically sized, self-handling button to clear a targeted Input."""
    def __init__(
        self,
        target_input: str | None = None,
        label: str = "Clear",
        **kwargs
        ) -> None:

        super().__init__(
            label=label,
            variant="error",
            **kwargs
        )
        self.target_input = target_input

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Automatically clear and refocus target input when clicked."""
        if self.target_input is not None:
            self.app.query_one(self.target_input, Input).clear()
            self.app.query_one(self.target_input, Input).focus()

class SourceGroup(Horizontal,FileValidator):
    def compose(self):
        self.ready = None
        yield Select([
                    ("Source Grid","grd"),
                    ("Weights File","wts")
                    ],
                    allow_blank = False,
                    id = "source_format"
                    )
        yield Input(placeholder = "/path/to/source/grd", id = "source_path", tooltip = "Path to the source fort.14.")
        yield ClearButton("#source_path")
        yield SelectFile(input_field_id="source_path", id="select_file_weights")

    def on_select_changed(self, event: Select.Changed) -> None:
        self.parent.mode = event.value

class SaveWeightsGroup(Horizontal,FileValidator):
    def compose(self):
        self.ready = None
        yield Checkbox("Save Weights",id = "save_weights_button")
        yield Input(placeholder = "weights.nc", id = "save_weights_path", tooltip = "Path to the location the file should be saved.")
        yield Static(classes="fixed-spacer",id = "placeholder")

    def on_mount(self):
        self.query_one("#save_weights_path").disabled = True

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        nput = self.query_one(Input)
        if event.value:
            nput.disabled = False
            self.check_file_path(nput)
            self.parent.paths_ready["save"] = self.ready
        else:
            nput.remove_class("-valid-file", "-invalid-file")
            nput.disabled = True
            self.parent.paths_ready["save"] = None
        self.parent.mutate_reactive(self.parent.__class__.paths_ready)

class LoadWeights(Horizontal):
    def compose(self):
        yield Button("Load weights",id = "load_weights_button",variant="success")
        yield ProgressBar(total=3, id = "load_weights_progressbar")

    def on_button_pressed(self):
        self.query_one("#load_weights_progressbar").update(progress = 0)
        self.parent.execute()

class InputGroup(VerticalGroup):
    def __init__(self, app, *args,**kwargs):
        super().__init__(*args,**kwargs)
        #TODO If the ui becomes dynamic, these need to become querries instead of attributes
        self.text_app = app
        self.targetgroup = FilePickerRow("Target Grid","/path/to/target/grd",id = "target")
        self.saveweightsgroup = SaveWeightsGroup(id = "save")

    mode = reactive("grd")

    def watch_mode(self, mode):
        source_path = self.query_one("#source_path")
        if mode == "grd":
            source_path.placeholder = "/path/to/source/grd"
            source_path.tooltip = source_path.parent._original_tooltip = "Path to the source fort.14."
            self.targetgroup.disabled = False
            self.saveweightsgroup.disabled = False
        elif mode == "wts":
            source_path.placeholder = "/path/to/source/wts.nc"
            source_path.tooltip = source_path.parent._original_tooltip = "Path to a pre-calculated weights.nc file."
            self.targetgroup.disabled = True
            self.saveweightsgroup.disabled = True

        self.watch_paths_ready(self.paths_ready)

    paths_ready = reactive({"source":None,"target":None,"save":None})

    def watch_paths_ready(self, paths_ready):
        source_ready = paths_ready["source"]
        if not source_ready:
            self.input_ready = False
            return
        if self.mode == "wts":
            self.input_ready = True
        elif paths_ready["target"]:
            self.input_ready = paths_ready["save"] or paths_ready["save"] is None
        else:
            self.input_ready = False

    input_ready = reactive(False)
    
    def watch_input_ready(self, input_ready):
        disable = not input_ready
        self.query_one("#load_weights").disabled = disable
        if disable:
            self.app.disable_output = disable

    def on_mount(self):
        env_weights_path = os.getenv("CSTORM_INTERP_WEIGHTS")
        if env_weights_path:
            self.mode = "wts"
            source_path = self.query_one("#source_path")

            self.query_one("#source_format").value = "wts"
            source_path.value = env_weights_path
            source_path.tooltip = "Path to a pre-calculated weights.nc file."
            load_weights = self.query_one("#load_weights")
            load_weights.disabled = False
            load_weights.query_one(Button).focus()

    def compose(self):
        yield SourceGroup(id = "source")
        yield self.targetgroup
        yield self.saveweightsgroup
        yield LoadWeights(id = "load_weights")

    #TODO Move this out and split up the function in cstorm_utils
    @work(thread=True)
    def execute(self):
        load_bar =  self.text_app.query_one("#load_weights_progressbar", ProgressBar)
        load_pbar = PBar(self.text_app, load_bar, call_back = lambda: (not setattr(self.app, "disable_output", False)
                                                                            and 
                                                                            self.app.log_interp(f"Updating PBar step...")))

        if self.mode == "wts":
            self.text_app.query_one("#load_weights_progressbar").update(total=2)
            load_bar.advance(1)
            weights = self.query_one("#source_path").value
            weights=[cu.CSTORM_U2U,cu.CSTORM_U2S][0].load(weights)
            load_bar.advance(1)
            source_grd = None
            target_grd = None
            save_weights = None
        else:
            source_grd = self.query_one("#source_path").value
            target_grd = self.query_one("#target_path").value
            save_weights_checked = self.query_one("#save_weights_button").value
            if save_weights_checked:
                save_weights = self.query_one("#save_weights_path").value or True #If value is an empty string return True
                self.text_app.query_one("#load_weights_progressbar").update(total=10)
            else:
                save_weights = False

            self.app.log_interp(f"Beginning to read sources...")
            unstruct_kwargs,target_kwargs,target_grd_key = cu.read_sources(source_grd, target_grd, pbar=load_pbar)
            self.app.log_interp(f"Done reading sources!!!")
            weights={"nodes":cu.CSTORM_U2U,"mesh":cu.CSTORM_U2S}[target_grd_key](unstruct_kwargs,target_kwargs)
            load_bar.advance(1)
            if save_weights_checked:
                self.app.log_interp(f"Saving Weights...")
                weights.save(save_weights, pbar=load_pbar)
                self.app.log_interp(f"Weights saved!!!")

        self.app.log_interp(f"Running weights with options:\n\tsource_grd : {source_grd}\n\ttarget_grd : {target_grd}\n\tsave_weights : {save_weights}\n\tweights : {weights}\n")
        setattr(self.app, "disable_output", False)

class OptionsGroup(Horizontal):
    def compose(self):
            yield Checkbox("Compress", id = "compress_check_box")
            yield Select([
                ("depth","depth"),
                ("extreme","extreme"),
                ("timed","timed"),
            ],
            prompt = "Interp type",
            id = "interp_type_select")
            yield Select([
                ("0",0),
                ("1",1),
            ],
            prompt = "Fix dry method (default = 0)",
            id = "fix_dry_select")
            yield Input(placeholder="Pool cap",id = "pool_cap_input",type="integer")
            yield Checkbox("Quite", id = "quite_check_box")

class RunInterp(Horizontal):
    def compose(self):
        yield Button("Run Interp",id = "run_interp_button",variant="success")
        with Horizontal(id = "progress_bars_vertical"):
            #with Horizontal(id = "interp_horizontal_group"):
            yield Label("Interpolation",id = "interp_label")
            yield ProgressBar(total=100, id = "interp_progres_bar")

            #with Horizontal(id = "write_horizontal_group"):
            yield Label("Writing",id = "write_label")
            yield ProgressBar(total=100, id = "write_progres_bar")

    def on_button_pressed(self):
            self.query_one("#interp_progres_bar").update(progress = 0)
            self.query_one("#write_progres_bar").update(progress = 0)
            self.parent.execute()
#            self.app._advance_pbar(self.query_one("#interp_progres_bar"), # This is the most shit soup sandwich of a line of code I have ever written, but it works 
#                                   call_back = lambda: (self.app.log_interp("Interped data\n")
#                                                        or
#                                                        self.app._advance_pbar(
#                                                            self.query_one("#write_progres_bar"),
#                                                            call_back = lambda: self.app.log_interp("Wrote data\n")
#                                                        )))

class OutputGroup(VerticalGroup):

    paths_ready = reactive({"source_data":None})

    def watch_paths_ready(self, paths_ready):
        self.query_one("#run_interp").disabled = not bool(paths_ready["source_data"])

    def watch_disabled(self, disabled):
        super().watch_disabled(disabled)
        if self.is_mounted:
            self.watch_paths_ready(self.paths_ready)

    def compose(self):
        yield FilePickerRow("Source data", "/path/to/data", id = "source_data")
        output_path = FilePickerRow("Output path", "interp.out", id = "output")
        output_path.new_file = True
        yield output_path
        yield OptionsGroup(id = "options_group")
        yield RunInterp(id = "run_interp")

    def _execute_interp(self,data_path,out_path,fix_dry,interp_type,compress,quite):
        self.app.log_interp(f"Running interp with options:\n\tdata_path : {data_path}\n\tout_path : {out_path}\n\tfix_dry : {fix_dry}\n\tinterp_type : {interp_type}\n\tcompress : {compress}\n\tquite : {quite}\n")
        self.app._advance_pbar(self.query_one("#interp_progres_bar"),call_back = self._execute_write)
                
    def _execute_write(self):
        self.app.log_interp(f"Interp completed")
        self.app._advance_pbar(self.query_one("#write_progres_bar"),call_back = lambda: self.app.log_interp(f"Data written"))

    def execute(self):
        data_path = self.query_one("#source_data_path").value
        out_path = self.query_one("#output_path").value
        fix_dry = self.query_one("#fix_dry_select").value
        if fix_dry is Select.NULL:
            fix_dry = 0
        interp_type = self.query_one("#interp_type_select").value
        if interp_type is Select.NULL:
                    interp_type = None
        compress = self.query_one("#compress_check_box").value
        quite = self.query_one("#quite_check_box").value
        self._execute_interp(data_path,out_path,fix_dry,interp_type,compress,quite)
        


class FullWidthLogHeader(Label):
    """A full-width banner label to denote the start of the log output section."""

    def __init__(self, text: str = "LOG", **kwargs) -> None:
        super().__init__(text, **kwargs)

class PBar:
    def __init__(self, app, pbar: ProgressBar, call_back = None, *args,**kwargs) -> None:
        super().__init__()
        self.text_app = app
        self.pbar = pbar
        self.call_back = call_back
    
    def update(self, amount: int = 1):
        self.text_app.call_from_thread(self.pbar.advance, amount)

        if self.call_back:
            self.text_app.call_from_thread(self.call_back)

class InterpApp(App):
    """A Textual app to manage stopwatches."""
    CSS_PATH = "interp_app.tcss"
    disable_output = reactive(True)

    def watch_disable_output(self, disable_output):
        self.outputgroup.disabled = disable_output

    BINDINGS = [
                Binding("ctrl+d", "quit", "Quit", priority=True),
                Binding("escape", "unfocus", "Unfocus", priority=True),]

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.inputgroup = InputGroup(self)
        self.outputgroup = OutputGroup()
        self.textarea = Log()

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        with VerticalGroup(id = "main"):
            yield self.inputgroup
            yield self.outputgroup
            yield FullWidthLogHeader()
            yield self.textarea
        yield Footer()

    def action_unfocus(self) -> None:
        self.set_focus(None)

    def log_interp(self, message):
        self.textarea.write_line(message)

    def action_toggle_dark(self) -> None:
        """An action to toggle dark mode."""
        self.theme = (
            "textual-dark" if self.theme == "textual-light" else "textual-light"
        )

if __name__ == "__main__":
    app = InterpApp()
    app.run()