'''
mesoSPIM_ScriptWindow.py
========================
'''

import os
import sys
import time

from PyQt5 import QtWidgets, QtCore, QtGui

from .utils.utility_functions import fit_window_to_screen

class mesoSPIM_ScriptWindow(QtWidgets.QWidget):
    ''' At some point: Change this into a Factory class for creating script windows '''

    sig_execute_script = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.zoom_factor = 3

        self.setWindowTitle('mesoSPIM Script Editor')
        self.setGeometry(100, 100, 600, 800)
        fit_window_to_screen(self)

        self.LoadScriptButton = QtWidgets.QPushButton('Load Script')
        self.LoadScriptButton.setStyleSheet('QPushButton{font-size: 21px}')
        self.LoadScriptButton.clicked.connect(self.load_script)
        self.SaveScriptButton = QtWidgets.QPushButton('Save Script')
        self.SaveScriptButton.setStyleSheet('QPushButton{font-size: 21px}')
        self.SaveScriptButton.clicked.connect(self.save_script)
        self.ExecuteScriptButton = QtWidgets.QPushButton('Execute Script')
        self.ExecuteScriptButton.setStyleSheet('QPushButton{font-size: 21px}')
        self.ExecuteScriptButton.clicked.connect(self.execute_script)

        self.Editor = QtWidgets.QPlainTextEdit()
        self.Editor.zoomIn(self.zoom_factor)
        self.Editor.setTabStopWidth(20)
        # self.Editor.wheelEvent.connect(lambda: print('Wheel wheeled'))

        self.layout = QtWidgets.QGridLayout()
        self.layout.addWidget(self.Editor, 0, 0, 3, 3)
        self.layout.addWidget(self.LoadScriptButton, 4, 0, 1, 1)
        self.layout.addWidget(self.SaveScriptButton, 4, 1, 1, 1)
        self.layout.addWidget(self.ExecuteScriptButton, 4, 2, 1, 1)
        self.setLayout(self.layout)

        self.highlight = PythonHighlighter(self.Editor.document())

        ''' Connect parent signals '''
        if parent is not None:
            self.parent.sig_enable_gui.connect(lambda boolean: self.setEnabled(boolean))
            
        self.show()

    def load_script(self):
        '''Load a script

        The empty string in the method arguments ensures that it remembers the
        last location from where a file was opened.
        '''
        current_path = os.path.abspath('./scripts')
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Load script',current_path)

        ''' To avoid crashes, continue only when a file has been selected:'''
        if path:
            with open(path, 'r') as myscript:
                script = myscript.read()
                self.Editor.setPlainText(script)

    def save_script(self):
        ''' Save a script as .py file '''
        current_path = os.path.abspath('./scripts')
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Save File', current_path,
                                                        filter="*.py", initialFilter="*.py")
        if path:
            with open(path, 'w') as myscript:
                script = self.Editor.toPlainText()
                myscript.write(script)

    def execute_script(self):
        script = self.Editor.toPlainText()
        if __name__ == '__main__':
            ''' Allow this editor to be used as an stand-alone editor for testing '''
            exec(script)
        else:
            self.setEnabled(False)
            self.sig_execute_script.emit(script)


def format(color, style=''):
    '''Return a QTextCharFormat with the given attributes.'''
    _color = QtGui.QColor()
    _color.setNamedColor(color)

    _format = QtGui.QTextCharFormat()
    _format.setForeground(_color)
    if 'bold' in style:
        _format.setFontWeight(QtGui.QFont.Bold)
    if 'italic' in style:
        _format.setFontItalic(True)

    return _format


STYLES = {
    'keyword': format('#FF8C00', 'bold'),
    'builtin': format('#900090'),
    'operator': format('#8B0000'),
    'brace': format('#555555'),
    'defclass': format('#56B6C2', 'bold'),
    'string': format('#067D17'),
    'string2': format('#067D17'),
    'comment': format('#808080', 'italic'),
    'self': format('#8B008B', 'italic'),
    'numbers': format('#098658'),
    'decorator': format('#AA5500'),
}

class PythonHighlighter (QtGui.QSyntaxHighlighter):
    """Syntax highlighter for the Python language.
    """
    keywords = [
        'and', 'as', 'assert', 'async', 'await', 'break', 'class',
        'continue', 'def', 'del', 'elif', 'else', 'except', 'finally',
        'for', 'from', 'global', 'if', 'import', 'in', 'is', 'lambda',
        'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'try',
        'while', 'with', 'yield', 'None', 'True', 'False',
    ]

    builtins = [
        'abs', 'all', 'any', 'bin', 'bool', 'bytes', 'callable', 'chr',
        'dict', 'dir', 'enumerate', 'eval', 'exec', 'filter', 'float',
        'format', 'frozenset', 'getattr', 'globals', 'hasattr', 'hash',
        'hex', 'id', 'input', 'int', 'isinstance', 'issubclass', 'iter',
        'len', 'list', 'locals', 'map', 'max', 'min', 'next', 'object',
        'oct', 'open', 'ord', 'pow', 'print', 'property', 'range',
        'repr', 'reversed', 'round', 'set', 'setattr', 'slice', 'sorted',
        'staticmethod', 'str', 'sum', 'super', 'tuple', 'type', 'vars', 'zip',
    ]

    operators = [
        '=',
        '==', '!=', '<', '<=', '>', '>=',
        '\+', '-', '\*', '/', '//', '\%', '\*\*',
        '\+=', '-=', '\*=', '/=', '\%=',
        '\^', '\|', '\&', '\~', '>>', '<<',
    ]

    braces = [
        '\{', '\}', '\(', '\)', '\[', '\]',
    ]

    def __init__(self, document):
        QtGui.QSyntaxHighlighter.__init__(self, document)

        # Multi-line strings (expression, flag, style)
        # FIXME: The triple-quotes in these two lines will mess up the
        # syntax highlighting from this point onward
        self.tri_single = (QtCore.QRegExp("'''"), 1, STYLES['string2'])
        self.tri_double = (QtCore.QRegExp('"""'), 2, STYLES['string2'])

        rules = []

        rules += [(r'\b%s\b' % w, 0, STYLES['keyword'])
            for w in PythonHighlighter.keywords]
        rules += [(r'\b%s\b' % b, 0, STYLES['builtin'])
            for b in PythonHighlighter.builtins]
        rules += [(r'%s' % o, 0, STYLES['operator'])
            for o in PythonHighlighter.operators]
        rules += [(r'%s' % b, 0, STYLES['brace'])
            for b in PythonHighlighter.braces]

        rules += [
            (r'\bself\b', 0, STYLES['self']),
            (r'@\w+', 0, STYLES['decorator']),
            (r'"[^"\\]*(\\.[^"\\]*)*"', 0, STYLES['string']),
            (r"'[^'\\]*(\\.[^'\\]*)*'", 0, STYLES['string']),
            (r'\bdef\b\s*(\w+)', 1, STYLES['defclass']),
            (r'\bclass\b\s*(\w+)', 1, STYLES['defclass']),
            (r'#[^\n]*', 0, STYLES['comment']),
            (r'\b[+-]?[0-9]+[lL]?\b', 0, STYLES['numbers']),
            (r'\b[+-]?0[xX][0-9A-Fa-f]+[lL]?\b', 0, STYLES['numbers']),
            (r'\b[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\b', 0, STYLES['numbers']),
        ]

        # Build a QRegExp for each pattern
        self.rules = [(QtCore.QRegExp(pat), index, fmt)
            for (pat, index, fmt) in rules]


    def highlightBlock(self, text):
        """Apply syntax highlighting to the given block of text.
        """
        # Do other syntax formatting
        for expression, nth, format in self.rules:
            index = expression.indexIn(text, 0)

            while index >= 0:
                # We actually want the index of the nth match
                index = expression.pos(nth)
                length = len(expression.cap(nth))
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)

        self.setCurrentBlockState(0)

        # Do multi-line strings
        in_multiline = self.match_multiline(text, *self.tri_single)
        if not in_multiline:
            in_multiline = self.match_multiline(text, *self.tri_double)


    def match_multiline(self, text, delimiter, in_state, style):
        """Do highlighting of multi-line strings. ``delimiter`` should be a
        ``QRegExp`` for triple-single-quotes or triple-double-quotes, and
        ``in_state`` should be a unique integer to represent the corresponding
        state changes when inside those strings. Returns True if we're still
        inside a multi-line string when this function is finished.
        """
        # If inside triple-single quotes, start at 0
        if self.previousBlockState() == in_state:
            start = 0
            add = 0
        # Otherwise, look for the delimiter on this line
        else:
            start = delimiter.indexIn(text)
            # Move past this match
            add = delimiter.matchedLength()

        # As long as there's a delimiter match on this line...
        while start >= 0:
            # Look for the ending delimiter
            end = delimiter.indexIn(text, start + add)
            # Ending delimiter on this line?
            if end >= add:
                length = end - start + add + delimiter.matchedLength()
                self.setCurrentBlockState(0)
            # No; multi-line string
            else:
                self.setCurrentBlockState(in_state)
                length = len(text) - start + add
            # Apply formatting
            self.setFormat(start, length, style)
            # Look for the next match
            start = delimiter.indexIn(text, start + length)

        # Return True if still inside a multi-line string, False otherwise
        if self.currentBlockState() == in_state:
            return True
        else:
            return False

if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    window = mesoSPIM_ScriptWindow()
    sys.exit(app.exec_())
