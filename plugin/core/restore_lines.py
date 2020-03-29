import sublime
from .typing import Any, Dict, List


class RestoreLines:
    def __init__(self) -> None:
        self.saved_lines = []  # type: List[dict]

    def save_lines(self, locations: List[int], view: sublime.View) -> None:
        change_id = view.change_id()

        for point in locations:
            line = view.line(point)
            change_region = (line.begin(), line.end())
            text = view.substr(line)

            self.saved_lines.append({
                "change_id": change_id,
                "change_region": change_region,
                "text": text,
                # cursor will be use retore the cursor the te exact position
                "cursor": point
            })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "saved_lines": self.saved_lines
        }

    @staticmethod
    def from_dict(dictionary: Dict[str, Any]) -> 'RestoreLines':
        restore_lines = RestoreLines()
        restore_lines.saved_lines = dictionary["saved_lines"]
        return restore_lines

    def restore_lines(self, edit: sublime.Edit, view: sublime.View) -> None:
        # restore lines contents
        # insert back lines from the bottom to top
        for saved_line in reversed(self.saved_lines):
            change_id = saved_line['change_id']
            begin, end = saved_line['change_region']
            change_region = sublime.Region(begin, end)

            transform_region = view.transform_region_from(change_region, change_id)
            view.erase(edit, transform_region)
            view.insert(edit, transform_region.begin(), saved_line['text'])

        # restore old cursor position
        view.sel().clear()
        for saved_line in self.saved_lines:
            view.sel().add(saved_line["cursor"])
