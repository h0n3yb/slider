import { useState, KeyboardEvent } from 'react';
import { search } from '../utils/api';
import LoadingSpinner from './LoadingSpinner';

interface OutputData {
  bio?: string;
  email?: string;
  error?: string;
}

export default function SingleLead() {
  const [leadName, setLeadName] = useState('');
  const [additionalInfo, setAdditionalInfo] = useState('');
  const [loading, setLoading] = useState(false);
  const [output, setOutput] = useState<OutputData | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  const handleGenerate = async () => {
    if (isGenerating) return;
    setIsGenerating(true);
    setLoading(true);
    const [firstName, lastName] = leadName.split(' ');
    const companyName = additionalInfo.trim();

    try {
      const data = await search(firstName, lastName, companyName);
      setOutput(data.output);
      console.log("API response:", data);
    } catch (error) {
      setOutput({ error: "Search failed. Please try again." });
    }
    setLoading(false);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>) => { 
    if (e.key === 'Enter' && !e.shiftKey) { 
      e.preventDefault(); 
      handleGenerate(); 
    } 
  }; 

  return (
    <div className="space-y-4">
      <input 
        type="text" 
        value={leadName}
        onChange={(e) => setLeadName(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Enter Lead Name"
        className="w-full px-4 py-3 rounded-lg bg-white text-[#000000] placeholder-[#D3D3D3] focus:outline-none focus:ring-2 focus:ring-[#8f99fb] focus:ring-opacity-50"
      />
      <textarea 
        value={additionalInfo}
        onChange={(e) => setAdditionalInfo(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Enter any information to use or guide bio generation"
        className="w-full px-4 py-3 rounded-lg bg-white text-[#000000] placeholder-[#D3D3D3] focus:outline-none focus:ring-2 focus:ring-[#8f99fb] focus:ring-opacity-50"
        rows={4}
      />
      
      {!isGenerating && (
        <button 
          onClick={handleGenerate}
          className="w-full py-3 bg-[#7A85E1] text-white font-semibold rounded-lg hover:bg-opacity-90 focus:outline-none focus:ring-2 focus:ring-[#7A85E1] focus:ring-opacity-50 shadow-md"
        >
          Generate
        </button>
      )}
      
      {loading && <LoadingSpinner />}
      
      {output && (
        <div className="mt-4 p-4 bg-white rounded-lg shadow-md">
          {output.error ? (
            <p className="text-red-500">{output.error}</p>
          ) : (
            <>
              <p className="text-[#000000] mb-2">{output.bio}</p>
              <p className="text-[#000000]">Email: {output.email}</p>
            </>
          )}
        </div>
      )}
    </div>
  );
}