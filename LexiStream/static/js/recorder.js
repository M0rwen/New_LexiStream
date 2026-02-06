// Audio Recording functionality
let mediaRecorder;
let audioChunks = [];
let startTime;
let timerInterval;
let duration = 0;

const startRecordBtn = document.getElementById('startRecord');
const stopRecordBtn = document.getElementById('stopRecord');
const recordingStatus = document.getElementById('recordingStatus');
const timer = document.getElementById('timer');
const audioPlayback = document.getElementById('audioPlayback');
const recordForm = document.getElementById('recordForm');
const audioFileInput = document.getElementById('audioFile');
const durationInput = document.getElementById('durationInput');

if (startRecordBtn) {
    startRecordBtn.addEventListener('click', startRecording);
}

if (stopRecordBtn) {
    stopRecordBtn.addEventListener('click', stopRecording);
}

async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = (event) => {
            audioChunks.push(event.data);
        };

        mediaRecorder.onstop = () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
            const audioUrl = URL.createObjectURL(audioBlob);
            audioPlayback.src = audioUrl;
            audioPlayback.style.display = 'block';

            // Create file input
            const file = new File([audioBlob], `recording_${Date.now()}.wav`, { type: 'audio/wav' });
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(file);
            audioFileInput.files = dataTransfer.files;

            // Set duration
            durationInput.value = duration;

            // Stop all tracks
            stream.getTracks().forEach(track => track.stop());
        };

        mediaRecorder.start();
        startTime = Date.now();
        startRecordBtn.disabled = true;
        stopRecordBtn.disabled = false;
        recordingStatus.textContent = '● Recording...';
        recordingStatus.classList.add('recording');

        // Start timer
        timerInterval = setInterval(updateTimer, 100);
    } catch (error) {
        console.error('Error accessing microphone:', error);
        alert('Error accessing microphone. Please check your permissions.');
    }
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
        clearInterval(timerInterval);
        startRecordBtn.disabled = false;
        stopRecordBtn.disabled = true;
        recordingStatus.textContent = '✓ Recording complete';
        recordingStatus.classList.remove('recording');
        recordForm.style.display = 'block';
    }
}

function updateTimer() {
    duration = (Date.now() - startTime) / 1000;
    const minutes = Math.floor(duration / 60);
    const seconds = Math.floor(duration % 60);
    timer.textContent = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}
