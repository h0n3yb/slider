document.addEventListener('DOMContentLoaded', function () {
  const generateButton = document.getElementById('generate');
  const loadingSpinner = document.getElementById('loading-spinner');
  const outputContainer = document.getElementById('output-container');
  const leadNameInput = document.getElementById('leadName');
  const additionalInfoInput = document.getElementById('additionalInfo');

  const singleLeadTab = document.getElementById('singleLeadTab');
  const batchUploadTab = document.getElementById('batchUploadTab');
  const singleLeadContent = document.getElementById('singleLeadContent');
  const batchUploadContent = document.getElementById('batchUploadContent');
  const generateBatchButton = document.getElementById('generateBatch');

  const csvFileInput = document.getElementById('csvFile');
  const fileNameDisplay = document.getElementById('fileNameDisplay');

  // Function to trigger button click on Enter key press
  function handleEnterKey(event) {
    if (event.key === "Enter") {
      event.preventDefault();
      event.target.blur();
      generateButton.click();
    }
  }

  // Add event listeners to input fields
  leadNameInput.addEventListener('keypress', handleEnterKey);
  additionalInfoInput.addEventListener('keypress', handleEnterKey);

  // Hide the loading spinner and output container initially
  loadingSpinner.style.display = 'none';
  outputContainer.style.display = 'none';

  generateButton.addEventListener('click', function () {
    const leadName = document.getElementById('leadName').value;
    const additionalInfo = document.getElementById('additionalInfo').value;
    const outputContainer = document.getElementById('output-container');
    
    // Clear the output container
    outputContainer.innerHTML = '';

    const [firstName, lastName] = leadName.split(' ');
    const companyName = additionalInfo.trim();

    // Show the loading spinner and disable the button
    loadingSpinner.style.display = 'flex';
    generateButton.disabled = true;

    search(firstName, lastName, companyName)
      .then(data => {
        // Hide the loading spinner and enable the button
        loadingSpinner.style.display = 'none';
        generateButton.disabled = false;

        if (data.output) {
          console.log("Generated Lead:", data.output);
          displayGeneratedBio(data.output);
        } else if (data.error) {
          console.error("Error:", data.error);
          displayError(data.error);
        }
      })
      .catch(error => {
        // Hide the loading spinner and enable the button
        loadingSpinner.style.display = 'none';
        generateButton.disabled = false;

        console.error("Search failed:", error);
        displayError("Search failed. Please try again.");
      });
  }, false);

  singleLeadTab.addEventListener('click', () => switchTab('singleLeadContent', singleLeadTab));
  batchUploadTab.addEventListener('click', () => switchTab('batchUploadContent', batchUploadTab));

  generateBatchButton.addEventListener('click', handleBatchGeneration);

  csvFileInput.addEventListener('change', function(event) {
    if (event.target.files.length > 0) {
      fileNameDisplay.textContent = `Uploaded: ${event.target.files[0].name}`;
      generateBatchButton.style.display = 'block';
    } else {
      fileNameDisplay.textContent = '';
      generateBatchButton.style.display = 'none';
    }
  });
});

function search(first, last, company) {
  const url = "http://localhost:5000/generate_bio";
  const payload = {
    first: first,
    last: last,
    company: company
  };

  return fetch(url, {
    method: "POST",
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  })
    .then(response => {
      if (!response.ok) {
        throw new Error('Network response was not ok');
      }
      return response.json();
    })
    .catch(error => {
      console.error('Error:', error);
      throw error;
    });
}

function displayGeneratedBio(leadObj) {
  const outputContainer = document.getElementById('output-container');

  const bioContainer = document.createElement('div');
  bioContainer.innerHTML = `
    <p>${leadObj.bio}</p>
    <p>Email: ${leadObj.email}</p>
  `;

  outputContainer.innerHTML = '';
  outputContainer.appendChild(bioContainer);
  outputContainer.style.display = 'block';
  
  // Add the show class after a short delay
  setTimeout(() => {
    outputContainer.classList.add('show');
  }, 100);
}

function displayError(errorMessage) {
  const outputContainer = document.getElementById('output-container');

  const errorElement = document.createElement('p');
  errorElement.textContent = errorMessage;
  errorElement.style.color = 'red';

  outputContainer.innerHTML = '';
  outputContainer.appendChild(errorElement);
  outputContainer.style.display = 'block';
}

function switchTab(tabName, clickedTab) {
  const tabcontents = document.getElementsByClassName('tabcontent');
  for (let i = 0; i < tabcontents.length; i++) {
    tabcontents[i].style.display = 'none';
  }
  document.getElementById(tabName).style.display = 'block';

  const tablinks = document.getElementsByClassName('tablinks');
  for (let i = 0; i < tablinks.length; i++) {
    tablinks[i].classList.remove('active');
  }
  clickedTab.classList.add('active');
}

function handleBatchGeneration() {
  const file = document.getElementById('csvFile').files[0];
  if (file) {
    const loadingSpinner = document.getElementById('loading-spinner');
    const generateBatchButton = document.getElementById('generateBatch');
    const fileUploadLabel = document.querySelector('.file-upload-label');
    const fileNameDisplay = document.getElementById('fileNameDisplay');
    
    // Hide the generate button, file upload button, and file name display
    generateBatchButton.style.display = 'none';
    fileUploadLabel.style.display = 'none';
    fileNameDisplay.style.display = 'none';
    
    // Show the loading spinner
    loadingSpinner.style.display = 'flex';
    
    // Create FormData object
    const formData = new FormData();
    formData.append('file', file);

    // Send the file to your server
    fetch('http://localhost:5000/generate_batch_bio', {
      method: 'POST',
      body: formData
    })
    .then(response => response.json())
    .then(data => {
      // Hide the loading spinner
      loadingSpinner.style.display = 'none';
      
      // Generate and download CSV
      downloadCSV(data.results);
      
      // Show the file upload button again and reset the file input
      fileUploadLabel.style.display = 'inline-flex';
      document.getElementById('csvFile').value = '';
      fileNameDisplay.textContent = '';
    })
    .catch(error => {
      console.error('Error:', error);
      loadingSpinner.style.display = 'none';
      displayError("Batch processing failed. Please try again.");
      
      // Show the file upload button again
      fileUploadLabel.style.display = 'inline-flex';
    });
  } else {
    displayError("Please select a CSV file first.");
  }
}

function downloadCSV(results) {
  let csvContent = "data:text/csv;charset=utf-8,";
  csvContent += "Name,Company,Email,Bio\n";
  
  results.forEach(result => {
    const row = [
      result.name,
      result.company,
      result.email,
      result.bio
    ].map(e => e ? `"${e.replace(/"/g, '""')}"` : "").join(",");
    csvContent += row + "\n";
  });

  const encodedUri = encodeURI(csvContent);
  const link = document.createElement("a");
  link.setAttribute("href", encodedUri);
  link.setAttribute("download", "generated_bios.csv");
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}