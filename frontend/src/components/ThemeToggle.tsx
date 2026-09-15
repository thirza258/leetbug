import { Moon, Sun } from 'lucide-react';
import { useTheme } from '../lib/theme';

export default function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const target = theme === 'light' ? 'dark' : 'light';
  return <button className="button secondary small theme-toggle" onClick={toggleTheme}
    aria-label={`Switch to ${target} theme`} title={`Switch to ${target} theme`}>
    {theme === 'light' ? <Moon size={16} /> : <Sun size={16} />}<span>{theme === 'light' ? 'Dark' : 'Light'} theme</span>
  </button>;
}
