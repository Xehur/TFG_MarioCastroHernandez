import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import {
  Search,
  Terminal,
  Loader2,
  AlertCircle,
  CheckCircle2,
  CornerDownLeft,
  Activity,
  Layers,
  Grid3x3,
  BarChart3,
  Download,
  Upload,
  MousePointer2,
  Square,
  Circle,
  Pentagon,
  Images,
  UploadCloud,
  Brain,
} from 'lucide-react';
import { commandService } from '../../../services/commandService';
import './CommandPalette.css';

const ICONS = {
  Activity,
  Layers,
  Grid3x3,
  BarChart3,
  Download,
  Upload,
  MousePointer2,
  Square,
  Circle,
  Pentagon,
  Images,
  UploadCloud,
  Brain,
};

const CommandIcon = ({ name }) => {
  const Icon = ICONS[name] || Terminal;
  return <Icon size={16} />;
};

/** Normaliza texto (minúsculas, sin acentos) para búsqueda tolerante. */
const normalize = text =>
  (text || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');

/**
 * Paleta de comandos (issue 40).
 *
 * Modal accesible con Ctrl/Cmd+K que lista los comandos disponibles agrupados
 * por categoría, con búsqueda en tiempo real y navegación por teclado. Al
 * seleccionar un comando: si es de servidor lo ejecuta vía API; si es de UI,
 * delega en `onCommand` para que el contenedor realice la acción.
 *
 * Props:
 * - context: { imageId } — parámetros disponibles para comandos de servidor.
 * - onCommand(command): maneja los comandos de tipo frontend (navegar, abrir
 *   dashboard, cambiar herramienta, exportar/importar, etc.).
 */
const CommandPalette = ({ context = {}, onCommand }) => {
  const [open, setOpen] = useState(false);
  const [commands, setCommands] = useState([]);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const [status, setStatus] = useState('idle'); // idle | running | error | success
  const [message, setMessage] = useState(null);

  const inputRef = useRef(null);
  const listRef = useRef(null);
  // Solo autodesplazamos el elemento activo cuando el usuario navega con el
  // teclado, no al abrir la paleta ni al mover el ratón (evita el "salto").
  const navByKeyRef = useRef(false);

  // Atajo global Ctrl/Cmd+K para abrir/cerrar la paleta.
  useEffect(() => {
    const onKeyDown = e => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen(prev => !prev);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  // Cargar comandos al abrir y resetear estado.
  useEffect(() => {
    if (!open) return;
    setQuery('');
    setActiveIndex(0);
    setStatus('idle');
    setMessage(null);
    commandService
      .getCommands()
      .then(data => {
        setCommands(data.commands || []);
        // La lista siempre arranca desde arriba al abrir.
        if (listRef.current) listRef.current.scrollTop = 0;
      })
      .catch(() => setCommands([]));
    // Enfocar el buscador tras el render (sin desplazar el contenedor).
    const id = setTimeout(() => inputRef.current?.focus({ preventScroll: true }), 0);
    return () => clearTimeout(id);
  }, [open]);

  const filtered = useMemo(() => {
    const q = normalize(query.trim());
    if (!q) return commands;
    return commands.filter(c => {
      const hay = normalize(
        `${c.name} ${c.description} ${c.category} ${(c.keywords || []).join(' ')}`
      );
      return hay.includes(q);
    });
  }, [commands, query]);

  // Agrupar por categoría preservando el orden.
  const groups = useMemo(() => {
    const map = new Map();
    filtered.forEach(c => {
      if (!map.has(c.category)) map.set(c.category, []);
      map.get(c.category).push(c);
    });
    return Array.from(map.entries());
  }, [filtered]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  const close = useCallback(() => setOpen(false), []);

  const runCommand = useCallback(
    async command => {
      if (!command) return;
      if (command.target === 'backend') {
        const params = {};
        // Rellenar parámetros conocidos desde el contexto.
        (command.params || []).forEach(p => {
          if (p.name === 'image_id' && context.imageId != null) {
            params.image_id = context.imageId;
          }
        });
        setStatus('running');
        setMessage(`Ejecutando “${command.name}”…`);
        try {
          const res = await commandService.executeCommand(command.id, params);
          setStatus('success');
          setMessage(res?.result?.message || `“${command.name}” completado.`);
          // Notifica al contenedor para que muestre el resultado (overlay, etc.).
          onCommand?.(command);
          setTimeout(() => setOpen(false), 900);
        } catch (err) {
          setStatus('error');
          setMessage(
            err.response?.data?.detail ||
              err.message ||
              'Error al ejecutar el comando.'
          );
        }
      } else {
        onCommand?.(command);
        setOpen(false);
      }
    },
    [context.imageId, onCommand]
  );

  const onKeyDown = e => {
    if (e.key === 'Escape') {
      e.preventDefault();
      close();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      navByKeyRef.current = true;
      setActiveIndex(i => Math.min(filtered.length - 1, i + 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      navByKeyRef.current = true;
      setActiveIndex(i => Math.max(0, i - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      runCommand(filtered[activeIndex]);
    }
  };

  // Mantener visible el elemento activo, solo al navegar con el teclado.
  useEffect(() => {
    if (!navByKeyRef.current) return;
    navByKeyRef.current = false;
    const el = listRef.current?.querySelector('[data-active="true"]');
    if (el && typeof el.scrollIntoView === 'function') {
      el.scrollIntoView({ block: 'nearest' });
    }
  }, [activeIndex]);

  if (!open) return null;

  // Índice plano por comando para resaltar el activo dentro de los grupos.
  let flatIndex = -1;

  return (
    <div className="cmd-overlay" onClick={close}>
      <div
        className="cmd-palette"
        role="dialog"
        aria-label="Paleta de comandos"
        onClick={e => e.stopPropagation()}
      >
        <div className="cmd-search">
          <Search size={18} />
          <input
            ref={inputRef}
            type="text"
            placeholder="Buscar comando…"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
          />
          <kbd className="cmd-kbd">Esc</kbd>
        </div>

        {message && (
          <div className={`cmd-status cmd-status-${status}`}>
            {status === 'running' && (
              <Loader2 size={15} className="cmd-spin" />
            )}
            {status === 'success' && <CheckCircle2 size={15} />}
            {status === 'error' && <AlertCircle size={15} />}
            <span>{message}</span>
          </div>
        )}

        <div className="cmd-list" ref={listRef}>
          {filtered.length === 0 ? (
            <p className="cmd-empty">No hay comandos que coincidan.</p>
          ) : (
            groups.map(([category, items]) => (
              <div key={category} className="cmd-group">
                <div className="cmd-group-title">{category}</div>
                {items.map(command => {
                  flatIndex += 1;
                  const isActive = flatIndex === activeIndex;
                  return (
                    <button
                      key={command.id}
                      type="button"
                      className="cmd-item"
                      data-active={isActive}
                      onMouseEnter={() => setActiveIndex(flatIndex)}
                      onClick={() => runCommand(command)}
                    >
                      <span className="cmd-item-icon">
                        <CommandIcon name={command.icon} />
                      </span>
                      <span className="cmd-item-text">
                        <span className="cmd-item-name">{command.name}</span>
                        <span className="cmd-item-desc">
                          {command.description}
                        </span>
                      </span>
                      {isActive && (
                        <span className="cmd-item-enter">
                          <CornerDownLeft size={14} />
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            ))
          )}
        </div>

        <div className="cmd-footer">
          <span>
            <kbd className="cmd-kbd">↑</kbd>
            <kbd className="cmd-kbd">↓</kbd> navegar
          </span>
          <span>
            <kbd className="cmd-kbd">↵</kbd> ejecutar
          </span>
          <span>
            <kbd className="cmd-kbd">Ctrl</kbd>
            <kbd className="cmd-kbd">K</kbd> abrir/cerrar
          </span>
        </div>
      </div>
    </div>
  );
};

export default CommandPalette;
