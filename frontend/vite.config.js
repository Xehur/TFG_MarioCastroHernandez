/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  esbuild: {
    jsxInject: `import React from 'react'`,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.js',
    css: false,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      // Cobertura centrada en los módulos con lógica testeable
      // (se excluye la capa OpenSeadragon/SVG, difícil de testear en jsdom).
      include: [
        'src/services/annotationService.js',
        'src/services/authService.js',
        'src/components/wsi/annotations/geometry.js',
        'src/components/wsi/annotations/useAnnotations.js',
        'src/components/wsi/annotations/AnnotationPanel.jsx',
        'src/components/wsi/annotations/AnnotationToolbar.jsx',
        'src/components/wsi/annotations/ClassificationModal.jsx',
        'src/components/wsi/annotations/CocoImportModal.jsx',
        'src/utils/apiError.js',
        'src/utils/helpers.js',
      ],
      thresholds: {
        lines: 75,
        functions: 75,
        branches: 75,
        statements: 75,
      },
    },
  },
});
