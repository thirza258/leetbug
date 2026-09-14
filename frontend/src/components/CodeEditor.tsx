import Editor, { loader } from '@monaco-editor/react';
import * as monaco from 'monaco-editor';
import EditorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker';
import TypeScriptWorker from 'monaco-editor/esm/vs/language/typescript/ts.worker?worker';
import type { Language } from '../types';

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

export default function CodeEditor({ language, value, onChange, readOnly = false }: {
  language: Language; value: string; onChange: (value: string) => void; readOnly?: boolean;
}) {
  return <Editor height="100%" language={language === 'cpp' ? 'cpp' : language} theme="leetbug"
    value={value} onChange={value => onChange(value ?? '')} loading={<span className="muted">Opening code editor…</span>}
    options={{ readOnly, minimap: { enabled: false }, fontSize: 13, lineHeight: 23,
      fontFamily: 'JetBrains Mono, monospace', fontLigatures: true, padding: { top: 22, bottom: 22 },
      scrollBeyondLastLine: false, automaticLayout: true, tabSize: 4, wordWrap: 'on',
      ariaLabel: 'Code editor', renderLineHighlight: 'line', folding: true, lineNumbersMinChars: 3 }} />;
}

