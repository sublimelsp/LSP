import sublime_plugin
from LSP.event_loop import run_future
from .view_async import open_view, save_view
from pathlib import Path

class LspExampleAsyncCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        print('1. this will be printed first')
        run_future(self.open_edit_save_and_close_file())
        print('2. This will printed second')

    async def open_edit_save_and_close_file(self):
        print('3. than this')
        w = self.view.window()
        if not w:
            return
        file_name = self.view.file_name()
        if not file_name:
            return
        readme_file = str((Path(file_name) / Path('../README.md')).resolve())
        view = await open_view(readme_file, w)
        view.run_command("append", {
            'characters': "LspExampleAsyncCommand added this" + '\n\n',
        })
        await save_view(view) 
        # the view is saved at this point and safe to be closed
        view.close()
