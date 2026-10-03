/* Iconos propios: 24×24, trazo de 1.75, mismas esquinas y remates en todos. */
const _svg = d => `<svg class="i" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
const ICON = {
  x:          _svg('<path d="M6 6l12 12M18 6L6 18"/>'),
  check:      _svg('<path d="M5 12.5l4.5 4.5L19 7.5"/>'),
  search:     _svg('<circle cx="11" cy="11" r="6"/><path d="M20 20l-4.2-4.2"/>'),
  plus:       _svg('<path d="M12 5v14M5 12h14"/>'),
  minus:      _svg('<path d="M5 12h14"/>'),
  external:   _svg('<path d="M14 4h6v6M20 4l-9 9M18 14v5H5V6h5"/>'),
  undo:       _svg('<path d="M9 7L4 12l5 5"/><path d="M4 12h10a5 5 0 0 1 0 10h-2"/>'),
  file:       _svg('<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4"/>'),
  cube:       _svg('<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9L12 3z"/><path d="M4 7.5l8 4.5 8-4.5M12 12v9"/>'),
  truck:      _svg('<path d="M2 6h12v9H2z"/><path d="M14 9h4l3 3v3h-7z"/><circle cx="6.5" cy="17.5" r="1.8"/><circle cx="17.5" cy="17.5" r="1.8"/>'),
  pallet:     _svg('<path d="M5 3h14v8H5z"/><path d="M2 13h20v3H2z"/><path d="M6 16v4M18 16v4M12 16v4"/>'),
  /* navegación */
  pedidos:    _svg('<path d="M7 3h10a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/><path d="M9 8h6M9 12h6M9 16h4"/>'),
  porhacer:   _svg('<path d="M4 6.5l1.8 1.8L9 5M4 12.5l1.8 1.8L9 11M4 18.5l1.8 1.8L9 17"/><path d="M12 7h8M12 13h8M12 19h8"/>'),
  cubicador:  _svg('<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9L12 3z"/><path d="M4 7.5l8 4.5 8-4.5M12 12v9"/>'),
  proyeccion: _svg('<path d="M5 5h14v15H5z"/><path d="M5 10h14M9 3v4M15 3v4"/>'),
  sap:        _svg('<path d="M4 8h13l-3-3M20 16H7l3 3"/>'),
  config:     _svg('<path d="M4 7h10M18 7h2M4 17h2M10 17h10M14 5v4M6 15v4"/>'),
};
