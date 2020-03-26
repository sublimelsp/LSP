import sublime
from .typing import List


class RestoreLines:
    def __init__(self):
        self.saved_lines = []  # type: List[dict]

    def save_lines(self, locations: List[int], view: sublime.View) -> None:
        # Clear previously saved lines
        self.clear()

        for point in locations:
            text = view.substr(view.line(point))
            row, _col = view.rowcol(point)

            self.saved_lines.append({
                "row": row,
                "text": text,
                # cursor will be use retore the cursor the te exact position
                "cursor": point
            })

    def to_dict(self):
        return {
            "saved_lines": self.saved_lines
        }

    @staticmethod
    def from_dict(dictionary):
        restore_lines = RestoreLines()
        restore_lines.saved_lines = dictionary["saved_lines"]
        return restore_lines

    def restore_lines(self, edit: sublime.Edit, view: sublime.View) -> None:
        # insert back lines from the bottom to top
        self.saved_lines.reverse()

        # restore lines contents
        for saved_line in self.saved_lines:
            current_view_point = view.text_point(saved_line['row'], 0)
            current_line_region = view.line(current_view_point)
            view.replace(edit, current_line_region, saved_line['text'])

        # restore old cursor position
        view.sel().clear()
        for saved_line in self.saved_lines:
            view.sel().add(saved_line["cursor"])

        # the lines are restored, clear them
        self.clear()

    def clear(self) -> None:
        self.saved_lines = []
