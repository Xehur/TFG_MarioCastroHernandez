import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ImageViewer } from './pages/ImageViewer';
import ImageList from './pages/ImageList';
import Upload from './pages/Upload';
import './App.css';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<ImageList />} />
        <Route path="/upload" element={<Upload />} />
        <Route path="/viewer/:imageId" element={<ImageViewer />} />
      </Routes>
    </Router>
  );
}

export default App;
