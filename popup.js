document.addEventListener('DOMContentLoaded', function () {
  const generateButton = document.getElementById('generate');
  const loadingSpinner = document.getElementById('loading-spinner');
  const outputContainer = document.getElementById('output-container');
  const leadNameInput = document.getElementById('leadName');
  const additionalInfoInput = document.getElementById('additionalInfo');

  // Function to trigger button click on Enter key press
  function handleEnterKey(event) {
      if (event.key === "Enter") {
            event.preventDefault();
            event.target.blur()
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
    <p>Phone: ${leadObj.phone}</p>
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