import { MousePointer2, Square, Circle, Pentagon } from 'lucide-react';
import './AnnotationToolbar.css';

const TOOLS = [
  { id: 'select', label: 'Seleccionar', Icon: MousePointer2 },
  { id: 'rectangle', label: 'Rectángulo', Icon: Square },
  { id: 'circle', label: 'Círculo', Icon: Circle },
  { id: 'polygon', label: 'Polígono', Icon: Pentagon },
];

const PRESET_COLORS = ['#FF0000', '#00C853', '#2962FF', '#FFD600', '#AA00FF', '#FF6D00'];

/**
 * Barra de herramientas de anotación: selección de herramienta de dibujo,
 * color y control del grid.
 */
const AnnotationToolbar = ({ tool, onToolChange, color, onColorChange, grid, onGridChange }) => {
  return (
    <div className="annotation-toolbar">
      <div className="toolbar-group">
        {TOOLS.map(t => (
          <button
            key={t.id}
            className={`tool-btn ${tool === t.id ? 'active' : ''}`}
            onClick={e => {
              onToolChange(t.id);
              e.currentTarget.blur();
            }}
            title={t.label}
            type="button"
          >
            <span className="tool-icon">
              <t.Icon size={18} strokeWidth={2} />
            </span>
            <span className="tool-label">{t.label}</span>
          </button>
        ))}
      </div>

      <div className="toolbar-group toolbar-colors">
        <span className="toolbar-title">Color</span>
        {PRESET_COLORS.map(c => (
          <button
            key={c}
            className={`color-swatch ${color === c ? 'active' : ''}`}
            style={{ background: c }}
            onClick={() => onColorChange(c)}
            title={c}
            type="button"
          />
        ))}
        <input
          type="color"
          value={color}
          onChange={e => onColorChange(e.target.value)}
          className="color-input"
          title="Color personalizado"
        />
      </div>

      <div className="toolbar-group toolbar-grid">
        <label className="grid-toggle">
          <input
            type="checkbox"
            checked={grid.enabled}
            onChange={e => onGridChange({ ...grid, enabled: e.target.checked })}
          />
          Grid
        </label>
        {grid.enabled && (
          <>
            <label className="grid-field">
              Celda
              <input
                type="number"
                min="32"
                step="32"
                value={grid.size}
                onChange={e =>
                  onGridChange({ ...grid, size: Math.max(32, Number(e.target.value) || 32) })
                }
              />
              px
            </label>
            <label className="grid-field">
              Opacidad
              <input
                type="range"
                min="0.1"
                max="1"
                step="0.1"
                value={grid.opacity}
                onChange={e => onGridChange({ ...grid, opacity: Number(e.target.value) })}
              />
            </label>
          </>
        )}
      </div>

      {tool === 'polygon' && (
        <div className="toolbar-hint">
          Clic para añadir vértices · doble clic / Enter para cerrar · Esc para cancelar
        </div>
      )}
    </div>
  );
};

export default AnnotationToolbar;
