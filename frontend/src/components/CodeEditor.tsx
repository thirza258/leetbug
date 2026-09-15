import Editor, { loader } from '@monaco-editor/react';
import * as monaco from 'monaco-editor/editor/editor.api';
import 'monaco-editor/editor/contrib/clipboard/browser/clipboard';
import 'monaco-editor/editor/contrib/find/browser/findController';
import 'monaco-editor/editor/contrib/folding/browser/folding';
import 'monaco-editor/editor/contrib/bracketMatching/browser/bracketMatching';
import 'monaco-editor/editor/contrib/comment/browser/comment';
import 'monaco-editor/editor/contrib/suggest/browser/suggestController';
import 'monaco-editor/languages/definitions/python/register';
import 'monaco-editor/languages/definitions/java/register';
import 'monaco-editor/languages/definitions/javascript/register';
import 'monaco-editor/languages/definitions/cpp/register';
import 'monaco-editor/languages/definitions/go/register';
import 'monaco-editor/languages/features/typescript/register';
import EditorWorker from 'monaco-editor/editor/editor.worker?worker';
import TypeScriptWorker from 'monaco-editor/languages/features/typescript/ts.worker?worker';
import type { Language } from '../types';
import { useTheme } from '../lib/theme';

self.MonacoEnvironment = {
  getWorker(_moduleId: string, label: string) {
    return label === 'typescript' || label === 'javascript' ? new TypeScriptWorker() : new EditorWorker();
  },
};
loader.config({ monaco });
monaco.editor.defineTheme('leetbug', {
  base: 'vs-dark', inherit: true,
  rules: [
    { token: 'comment', foreground: '697287', fontStyle: 'italic' },
    { token: 'keyword', foreground: 'BCA4F9' },
    { token: 'string', foreground: 'A8CF91' },
    { token: 'number', foreground: 'E7B97C' },
  ],
  colors: { 'editor.background': '#101219', 'editor.foreground': '#D5D8E4',
    'editorLineNumber.foreground': '#454B5D', 'editorLineNumber.activeForeground': '#A8ADC0',
    'editor.selectionBackground': '#36314D', 'editor.lineHighlightBackground': '#171A24',
    'editorCursor.foreground': '#B8A5F6', 'editor.inactiveSelectionBackground': '#28243B' },
});
monaco.editor.defineTheme('leetbug-light', {
  base: 'vs', inherit: true,
  rules: [
    { token: 'comment', foreground: '687386', fontStyle: 'italic' },
    { token: 'keyword', foreground: '6941A5' },
    { token: 'string', foreground: '246C41' },
    { token: 'number', foreground: '9A5900' },
  ],
  colors: { 'editor.background': '#FFFFFF', 'editor.foreground': '#202733',
    'editorLineNumber.foreground': '#8B94A4', 'editorLineNumber.activeForeground': '#465163',
    'editor.selectionBackground': '#E1D8F7', 'editor.lineHighlightBackground': '#F6F7FA',
    'editorCursor.foreground': '#6941A5', 'editor.inactiveSelectionBackground': '#EDE9F5' },
});

export default function CodeEditor({ language, value, onChange, readOnly = false }: {
  language: Language; value: string; onChange: (value: string) => void; readOnly?: boolean;
}) {
  const { theme } = useTheme();
  return <Editor height="100%" language={language === 'cpp' ? 'cpp' : language} theme={theme === 'dark' ? 'leetbug' : 'leetbug-light'}
    value={value} onChange={value => onChange(value ?? '')} loading={<span className="muted">Opening code editor…</span>}
    options={{ readOnly, minimap: { enabled: false }, fontSize: 13, lineHeight: 23,
      fontFamily: 'JetBrains Mono, monospace', fontLigatures: true, padding: { top: 22, bottom: 22 },
      scrollBeyondLastLine: false, automaticLayout: true, tabSize: 4, wordWrap: 'on',
      ariaLabel: 'Code editor', renderLineHighlight: 'line', folding: true, lineNumbersMinChars: 3 }} />;
}
