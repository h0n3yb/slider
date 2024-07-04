import { useState } from 'react';
import SingleLead from '../components/SingleLead';
import BatchUpload from '../components/BatchUpload';

export default function Home() {
  const [activeTab, setActiveTab] = useState('singleLead');

  return (
    <div className="min-h-screen bg-[#8f99fb] font-sans">
      <div className="container mx-auto px-4 py-8 max-w-md">
        <h1 className="text-3xl font-bold mb-6 text-white">Slider</h1>
        <div className="bg-white rounded-lg shadow-md mb-6">
          <div className="flex">
            <button 
              className={`flex-1 py-3 font-semibold rounded-tl-lg focus:outline-none focus:ring-2 focus:ring-[#8f99fb] focus:ring-opacity-50 shadow-md ${activeTab === 'singleLead' ? 'text-white bg-[#8f99fb]' : 'text-[#8f99fb] bg-white'}`}
              onClick={() => setActiveTab('singleLead')}
            >
              Single Lead
            </button>
            <button 
              className={`flex-1 py-3 font-semibold rounded-tr-lg focus:outline-none focus:ring-2 focus:ring-[#8f99fb] focus:ring-opacity-50 shadow-md ${activeTab === 'batchUpload' ? 'text-white bg-[#8f99fb]' : 'text-[#8f99fb] bg-white'}`}
              onClick={() => setActiveTab('batchUpload')}
            >
              Batch Upload
            </button>
          </div>
        </div>

        {activeTab === 'singleLead' ? <SingleLead /> : <BatchUpload />}
      </div>
    </div>
  );
}