import { useEffect, useRef, useState, useCallback } from 'react';
import { elementToImage, imageToElement, imageDistanceToElement, getImageSize } from './geometry';
import './AnnotationLayer.css';

/**
 * Capa SVG superpuesta al visor OpenSeadragon.
 *
 * Responsabilidades:
 * - Renderizar las anotaciones existentes en coordenadas de pantalla,
 *   sincronizándose con el zoom/desplazamiento del visor.
 * - Gestionar el dibujo de nuevas formas (rectángulo, círculo, polígono).
 * - Dibujar el grid configurable.
 *
 * Props:
 * - viewer: instancia de OpenSeadragon
 * - annotations: array de anotaciones
 * - tool: 'select' | 'rectangle' | 'circle' | 'polygon'
 * - color: color actual de dibujo
 * - selectedId: id de la anotación seleccionada
 * - onSelect(id): callback al seleccionar
 * - onCompleteShape({ shape_type, coordinates }): callback al terminar de dibujar
 * - grid: { enabled, size, opacity }
 */
const AnnotationLayer = ({
  viewer,
  annotations = [],
  tool = 'select',
  color = '#FF0000',
  selectedId = null,
  onSelect,
  onCompleteShape,
  onCancel,
  grid = { enabled: false, size: 256, opacity: 0.4 },
}) => {
  const svgRef = useRef(null);
  const [, setTick] = useState(0);
  const forceRender = useCallback(() => setTick(t => t + 1), []);

  const [size, setSize] = useState({ width: 0, height: 0 });
  // Estado de dibujo en curso (coordenadas de imagen)
  const [draft, setDraft] = useState(null);
  const [polygonPoints, setPolygonPoints] = useState([]);
  const [mouseImg, setMouseImg] = useState(null);

  const isDrawing = tool !== 'select';

  // Reiniciar el dibujo en curso al cambiar de herramienta (patrón recomendado:
  // ajustar estado durante el render en lugar de en un efecto).
  const [prevTool, setPrevTool] = useState(tool);
  if (tool !== prevTool) {
    setPrevTool(tool);
    setDraft(null);
    setPolygonPoints([]);
    setMouseImg(null);
  }

  // Sincronizar el overlay con los cambios de viewport del visor
  useEffect(() => {
    if (!viewer) return undefined;

    const update = () => {
      const el = viewer.element;
      if (el) {
        setSize({ width: el.clientWidth, height: el.clientHeight });
      }
      forceRender();
    };

    viewer.addHandler('update-viewport', update);
    viewer.addHandler('animation', update);
    viewer.addHandler('resize', update);
    viewer.addHandler('open', update);
    update();

    return () => {
      viewer.removeHandler('update-viewport', update);
      viewer.removeHandler('animation', update);
      viewer.removeHandler('resize', update);
      viewer.removeHandler('open', update);
    };
  }, [viewer, forceRender]);

  // Desactivar la navegación del visor mientras se dibuja
  useEffect(() => {
    if (!viewer) return;
    viewer.setMouseNavEnabled(!isDrawing);
  }, [viewer, isDrawing]);

  const getImgCoords = useCallback(
    e => {
      const rect = svgRef.current.getBoundingClientRect();
      const px = e.clientX - rect.left;
      const py = e.clientY - rect.top;
      return elementToImage(viewer, px, py);
    },
    [viewer]
  );

  // --- Dibujo: rectángulo y círculo (arrastrar) ---
  const handleMouseDown = e => {
    if (!isDrawing || !viewer) return;
    if (tool === 'polygon') return; // el polígono se maneja por clics
    e.preventDefault();
    const p = getImgCoords(e);
    setDraft({ start: p, current: p });
  };

  const handleMouseMove = e => {
    if (!viewer) return;
    if (draft && (tool === 'rectangle' || tool === 'circle')) {
      setDraft(d => ({ ...d, current: getImgCoords(e) }));
    } else if (tool === 'polygon' && polygonPoints.length > 0) {
      setMouseImg(getImgCoords(e));
    }
  };

  const handleMouseUp = e => {
    if (!isDrawing || !viewer || !draft) return;
    const end = getImgCoords(e);
    if (tool === 'rectangle') {
      const x = Math.min(draft.start.x, end.x);
      const y = Math.min(draft.start.y, end.y);
      const width = Math.abs(end.x - draft.start.x);
      const height = Math.abs(end.y - draft.start.y);
      setDraft(null);
      if (width > 2 && height > 2) {
        onCompleteShape({
          shape_type: 'rectangle',
          coordinates: {
            x: Math.round(x),
            y: Math.round(y),
            width: Math.round(width),
            height: Math.round(height),
          },
        });
      }
    } else if (tool === 'circle') {
      const radius = Math.hypot(end.x - draft.start.x, end.y - draft.start.y);
      setDraft(null);
      if (radius > 2) {
        onCompleteShape({
          shape_type: 'circle',
          coordinates: {
            x: Math.round(draft.start.x),
            y: Math.round(draft.start.y),
            radius: Math.round(radius),
          },
        });
      }
    }
  };

  // --- Dibujo: polígono (clic para añadir vértice, doble clic para cerrar) ---
  const handleClick = e => {
    if (tool !== 'polygon' || !viewer) return;
    const p = getImgCoords(e);
    setPolygonPoints(prev => [...prev, [Math.round(p.x), Math.round(p.y)]]);
  };

  const finishPolygon = useCallback(() => {
    if (polygonPoints.length >= 3) {
      onCompleteShape({
        shape_type: 'polygon',
        coordinates: { points: polygonPoints },
      });
    }
    setPolygonPoints([]);
    setMouseImg(null);
  }, [polygonPoints, onCompleteShape]);

  const cancelPolygon = useCallback(() => {
    setPolygonPoints([]);
    setMouseImg(null);
    if (onCancel) onCancel();
  }, [onCancel]);

  const handleDoubleClick = e => {
    if (tool !== 'polygon') return;
    e.preventDefault();
    finishPolygon();
  };

  // Cerrar polígono con Enter
  useEffect(() => {
    if (tool !== 'polygon') return undefined;
    const onKey = e => {
      if (e.key === 'Enter') finishPolygon();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [tool, finishPolygon]);

  // Cancelar cualquier figura en curso con Escape y volver a "Seleccionar"
  useEffect(() => {
    if (!isDrawing) return undefined;
    const onKey = e => {
      if (e.key === 'Escape') {
        setDraft(null);
        setPolygonPoints([]);
        setMouseImg(null);
        if (onCancel) onCancel();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isDrawing, onCancel]);

  if (!viewer) return null;

  // --- Render de cada anotación en coordenadas de pantalla ---
  const renderAnnotation = ann => {
    const c = ann.coordinates;
    const isSel = ann.id === selectedId;
    const common = {
      stroke: ann.color || color,
      strokeWidth: isSel ? 3 : 2,
      fill: ann.color || color,
      fillOpacity: isSel ? 0.25 : 0.12,
      style: { cursor: isDrawing ? 'crosshair' : 'pointer' },
      onClick: ev => {
        if (!isDrawing && onSelect) {
          ev.stopPropagation();
          onSelect(ann.id);
        }
      },
    };

    if (ann.shape_type === 'rectangle') {
      const tl = imageToElement(viewer, c.x, c.y);
      const w = imageDistanceToElement(viewer, c.width);
      const h = imageDistanceToElement(viewer, c.height);
      return <rect key={ann.id} x={tl.x} y={tl.y} width={w} height={h} {...common} />;
    }
    if (ann.shape_type === 'circle') {
      const center = imageToElement(viewer, c.x, c.y);
      const r = imageDistanceToElement(viewer, c.radius);
      return <circle key={ann.id} cx={center.x} cy={center.y} r={r} {...common} />;
    }
    if (ann.shape_type === 'polygon' && Array.isArray(c.points)) {
      const pts = c.points
        .map(p => {
          const e = imageToElement(viewer, p[0], p[1]);
          return `${e.x},${e.y}`;
        })
        .join(' ');
      return <polygon key={ann.id} points={pts} {...common} />;
    }
    return null;
  };

  // --- Render del dibujo en curso ---
  const renderDraft = () => {
    if (!draft) return null;
    if (tool === 'rectangle') {
      const x = Math.min(draft.start.x, draft.current.x);
      const y = Math.min(draft.start.y, draft.current.y);
      const tl = imageToElement(viewer, x, y);
      const w = imageDistanceToElement(viewer, Math.abs(draft.current.x - draft.start.x));
      const h = imageDistanceToElement(viewer, Math.abs(draft.current.y - draft.start.y));
      return (
        <rect
          x={tl.x}
          y={tl.y}
          width={w}
          height={h}
          stroke={color}
          strokeWidth={2}
          fill={color}
          fillOpacity={0.15}
          strokeDasharray="4"
        />
      );
    }
    if (tool === 'circle') {
      const center = imageToElement(viewer, draft.start.x, draft.start.y);
      const r = imageDistanceToElement(
        viewer,
        Math.hypot(draft.current.x - draft.start.x, draft.current.y - draft.start.y)
      );
      return (
        <circle
          cx={center.x}
          cy={center.y}
          r={r}
          stroke={color}
          strokeWidth={2}
          fill={color}
          fillOpacity={0.15}
          strokeDasharray="4"
        />
      );
    }
    return null;
  };

  const renderPolygonDraft = () => {
    if (tool !== 'polygon' || polygonPoints.length === 0) return null;
    const elPts = polygonPoints.map(p => imageToElement(viewer, p[0], p[1]));
    const linePts = [...elPts];
    if (mouseImg) linePts.push(imageToElement(viewer, mouseImg.x, mouseImg.y));
    const pointsStr = linePts.map(p => `${p.x},${p.y}`).join(' ');
    return (
      <g>
        <polyline
          points={pointsStr}
          stroke={color}
          strokeWidth={2}
          fill="none"
          strokeDasharray="4"
        />
        {elPts.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r={4} fill={color} />
        ))}
      </g>
    );
  };

  // --- Render del grid ---
  const renderGrid = () => {
    if (!grid.enabled) return null;
    const imgSize = getImageSize(viewer);
    if (!imgSize) return null;

    const spacing = imageDistanceToElement(viewer, grid.size);
    if (spacing < 6) return null; // demasiado denso, no dibujar

    const origin = imageToElement(viewer, 0, 0);
    const end = imageToElement(viewer, imgSize.width, imgSize.height);
    const lines = [];

    const startX = origin.x % spacing;
    for (let x = startX; x <= size.width; x += spacing) {
      lines.push(
        <line
          key={`v${x}`}
          x1={x}
          y1={Math.max(0, origin.y)}
          x2={x}
          y2={Math.min(size.height, end.y)}
          stroke="#00e5ff"
          strokeWidth={0.5}
        />
      );
    }
    const startY = origin.y % spacing;
    for (let y = startY; y <= size.height; y += spacing) {
      lines.push(
        <line
          key={`h${y}`}
          x1={Math.max(0, origin.x)}
          y1={y}
          x2={Math.min(size.width, end.x)}
          y2={y}
          stroke="#00e5ff"
          strokeWidth={0.5}
        />
      );
    }
    return <g opacity={grid.opacity}>{lines}</g>;
  };

  return (
    <>
      <svg
        ref={svgRef}
        className="annotation-layer"
        width={size.width}
        height={size.height}
        style={{
          pointerEvents: isDrawing ? 'auto' : 'none',
          cursor: isDrawing ? 'crosshair' : 'default',
        }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onClick={handleClick}
        onDoubleClick={handleDoubleClick}
      >
        {renderGrid()}
        <g style={{ pointerEvents: isDrawing ? 'none' : 'auto' }}>
          {annotations.map(renderAnnotation)}
        </g>
        {renderDraft()}
        {renderPolygonDraft()}
      </svg>

      {tool === 'polygon' && polygonPoints.length > 0 && (
        <div className="polygon-controls">
          <span className="polygon-count">{polygonPoints.length} punto(s)</span>
          <button
            type="button"
            className="polygon-btn finish"
            onClick={finishPolygon}
            disabled={polygonPoints.length < 3}
          >
            ✓ Finalizar
          </button>
          <button type="button" className="polygon-btn cancel" onClick={cancelPolygon}>
            ✕ Cancelar
          </button>
        </div>
      )}
    </>
  );
};

export default AnnotationLayer;
