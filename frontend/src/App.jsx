import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ImageViewer } from './pages/ImageViewer';
import './App.css';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/viewer/:imageId" element={<ImageViewer />} />
      </Routes>
    </Router>
  );
}

// Componente temporal Home
function Home() {
  return (
    <div style={{ padding: '40px', textAlign: 'center' }}>
      <h1>WSI Visualization System</h1>
      <p>Sistema de visualización de imágenes WSI</p>
      <p style={{ color: '#666', marginTop: '20px' }}>
        Para probar el visualizador, navega a: /viewer/[imageId]
      </p>
    </div>
  );
}

export default App;
