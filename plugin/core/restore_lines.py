import sublime

class RestoreLines:
    saved_lines = []

    def save_line(point, view):
        text = view.substr(view.line(point))
        row, _col = view.rowcol(point)

        RestoreLines.saved_lines.append({
            "row": row,
            "text": text,
            # cursor will be use retore the cursor the te exact position
            "cursor": point
        })

    def restore_lines(edit: sublime.Edit, view: sublime.View):
        # insert back lines from the bottom to top
        RestoreLines.saved_lines.reverse()

        # restore lines contents
        for saved_line in RestoreLines.saved_lines:
            current_view_point = view.text_point(saved_line['row'], 0)
            current_line_region = view.line(current_view_point)
            view.replace(edit, current_line_region, saved_line['text'])

        # restore old cursor position
        view.sel().clear()
        for saved_line in RestoreLines.saved_lines:
            view.sel().add(saved_line["cursor"])

        # the lines are restored, clear them
        RestoreLines.clear()

    def clear():
        RestoreLines.saved_lines = []