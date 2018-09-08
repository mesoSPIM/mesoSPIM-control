'''
mesoSPIM_ScriptWindow.py
========================
'''

import os
import sys
import time

from PyQt5 import QtWidgets, QtCore, QtGui

class mesoSPIM_ScriptWindow(QtWidgets.QWidget):
    ''' At some point: Change this into a Factory class for creating script windows '''

    sig_execute_script = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.zoom_factor = 3

        self.setWindowTitle('mesoSPIM Script Editor')
        self.setGeometry(1500,500,700,1000)

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
        # print(current_path)
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Load script',current_path)

        ''' To avoid crashes, continue only when a file has been selected:'''
        if path:
            with open(path, 'r') as myscript:
                script = myscript.read()
                self.Editor.setPlainText(script)

    def save_script(self):
        ''' Save a script '''
        current_path = os.path.abspath('./scripts')
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Save File',current_path)

        ''' To avoid crashes, continue only when a file has been selected:'''
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


# Syntax styles that can be shared by all languages
STYLES = {
    'keyword': format('purple'),
    'operator': format('red'),
    'brace': format('darkGray'),
    'defclass': format('black', 'bold'),
    'string': format('green'),
    'string2': format('green'),
    'comment': format('green', 'italic'),
    'self': format('red'),
    'numbers': format('brown'),
}

class PythonHighlighter (QtGui.QSyntaxHighlighter):
    """Syntax highlighter for the Python language.
    """
    # Python keywords
    keywords = [
        'and', 'assert', 'break', 'class', 'continue', 'def',
        'del', 'elif', 'else', 'except', 'exec', 'finally',
        'for', 'from', 'global', 'if', 'import', 'in',
        'is', 'lambda', 'not', 'or', 'pass', 'print',
        'raise', 'return', 'try', 'while', 'yield',
        'None', 'True', 'False',
    ]

    # Python operators
    operators = [
        '=',
        # Comparison
        '==', '!=', '<', '<=', '>', '>=',
        # Arithmetic
        '\+', '-', '\*', '/', '//', '\%', '\*\*',
        # In-place
        '\+=', '-=', '\*=', '/=', '\%=',
        # Bitwise
        '\^', '\|', '\&', '\~', '>>', '<<',
    ]

    # Python braces
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

        # Keyword, operator, and brace rules
        rules += [(r'\b%s\b' % w, 0, STYLES['keyword'])
            for w in PythonHighlighter.keywords]
        rules += [(r'%s' % o, 0, STYLES['operator'])
            for o in PythonHighlighter.operators]
        rules += [(r'%s' % b, 0, STYLES['brace'])
            for b in PythonHighlighter.braces]

        # All other rules
        rules += [
            # 'self'
            (r'\bself\b', 0, STYLES['self']),

            # Double-quoted string, possibly containing escape sequences
            (r'"[^"\\]*(\\.[^"\\]*)*"', 0, STYLES['string']),
            # Single-quoted string, possibly containing escape sequences
            (r"'[^'\\]*(\\.[^'\\]*)*'", 0, STYLES['string']),

            # 'def' followed by an identifier
            (r'\bdef\b\s*(\w+)', 1, STYLES['defclass']),
            # 'class' followed by an identifier
            (r'\bclass\b\s*(\w+)', 1, STYLES['defclass']),

            # From '#' until a newline
            (r'#[^\n]*', 0, STYLES['comment']),

            # Numeric literals
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
