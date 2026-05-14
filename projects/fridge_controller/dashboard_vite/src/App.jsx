import React, { useState } from 'react';
import Header from './components/Header';
import Tabs from './components/Tabs';
import LivePanel from './components/LivePanel';
import AnalysisPanel from './components/AnalysisPanel';
import ControlPanel from './components/ControlPanel';

function App() {
  const [activeTab, setActiveTab] = useState('live');

  return (
    <div className="app">
      <Header />
      <Tabs activeTab={activeTab} onChange={setActiveTab} />
      <main>
        {activeTab === 'live' && <LivePanel />}
        {activeTab === 'analysis' && <AnalysisPanel />}
        {activeTab === 'control' && <ControlPanel />}
      </main>
    </div>
  );
}

export default App;
