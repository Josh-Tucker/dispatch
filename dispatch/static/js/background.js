// Initialize WebGL context
const canvas = document.getElementById('canvas');
let startingWidth = window.innerWidth;
let startingHeight = window.innerHeight;
canvas.width = startingWidth;
canvas.height = startingHeight;
console.log("canvas width/height: "+canvas.width+" / "+canvas.height);

const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
let isPlaying = false;
let animationID = null;
let randomSeed = [Math.random(), Math.random(), Math.random()];
let time;
let timeOffset = 0;

// FPS tracking variables
let frameCount = 0;
let lastTime = 0;
let fps = 0;
const fpsIndicator = document.getElementById('fpsIndicator');

if (!gl) {
    alert('WebGL not supported');
}

// Compile shaders
function compileShader(source, type) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        console.error('Shader compilation error:', gl.getShaderInfoLog(shader));
        gl.deleteShader(shader);
        return null;
    }
    
    return shader;
}

// Create program
const vertexShader = compileShader(document.getElementById('vertexShader').textContent, gl.VERTEX_SHADER);
const fragmentShader = compileShader(document.getElementById('fragmentShader').textContent, gl.FRAGMENT_SHADER);

const program = gl.createProgram();
gl.attachShader(program, vertexShader);
gl.attachShader(program, fragmentShader);
gl.linkProgram(program);

if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    console.error('Program linking error:', gl.getProgramInfoLog(program));
}

gl.useProgram(program);

// Create rectangle covering the entire canvas
const positionBuffer = gl.createBuffer();
gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([
    -1.0, -1.0,
     1.0, -1.0,
    -1.0,  1.0,
     1.0,  1.0
]), gl.STATIC_DRAW);

// Set up attributes and uniforms
const positionLocation = gl.getAttribLocation(program, 'position');
gl.enableVertexAttribArray(positionLocation);
gl.vertexAttribPointer(positionLocation, 2, gl.FLOAT, false, 0, 0);

const timeLocation = gl.getUniformLocation(program, 'time');
const resolutionLocation = gl.getUniformLocation(program, 'resolution');
const seedLocation = gl.getUniformLocation(program, 'seed');

// GUI-controlled uniform locations
const timeScaleLocation = gl.getUniformLocation(program, 'timeScale');
const bloomStrengthLocation = gl.getUniformLocation(program, 'bloomStrength');
const saturationLocation = gl.getUniformLocation(program, 'saturation');
const grainAmountLocation = gl.getUniformLocation(program, 'grainAmount');
const colorTintLocation = gl.getUniformLocation(program, 'colorTint');
const minCircleSizeLocation = gl.getUniformLocation(program, 'minCircleSize');
const circleStrengthLocation = gl.getUniformLocation(program, 'circleStrength');
const distortXLocation = gl.getUniformLocation(program, 'distortX');
const distortYLocation = gl.getUniformLocation(program, 'distortY');

const patternAmpLocation = gl.getUniformLocation(program, 'patternAmp');
const patternFreqLocation = gl.getUniformLocation(program, 'patternFreq');

// Initialize parameters object for dat.gui
const params = {
    timeScale: 0.4,
    patternAmp: 12.0,
    patternFreq: 0.5,
    bloomStrength: 1.0,
    saturation: 0.85,
    grainAmount: 0.2,
    colorTintR: 1.0,
    colorTintG: 1.0, 
    colorTintB: 1.0,
    minCircleSize: 3.0,
    circleStrength: 1.0,
    distortX: 5.0,
    distortY: 20.0,
};

// Function to refresh the pattern with a new random seed
function refreshPattern() {
    randomSeed = [Math.random(), Math.random(), Math.random()];
    gl.uniform3f(seedLocation, randomSeed[0], randomSeed[1], randomSeed[2]);
    
    // Reset time offset to current time to restart animation
    timeOffset = time || 0;
}

// Handle window resize
function handleResize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    gl.viewport(0, 0, canvas.width, canvas.height);
}

window.addEventListener('resize', handleResize);

// Initialize dat.gui
const gui = new dat.GUI({ autoplace: false });
gui.close();

// Add GUI controls with folders for organization
const timeFolder = gui.addFolder('Animation');
timeFolder.add(params, 'timeScale', 0.1, 3.0).name('Speed').onChange(updateUniforms);
timeFolder.open();

const patternFolder = gui.addFolder('Pattern');
patternFolder.add(params, 'patternAmp', 1.0, 50.0).step(0.1).name('Pattern Amp').onChange(updateUniforms);
patternFolder.add(params, 'patternFreq', 0.2, 10.0).step(0.1).name('Pattern Freq').onChange(updateUniforms);
patternFolder.open();

const visualFolder = gui.addFolder('Visual Effects');
visualFolder.add(params, 'bloomStrength', 0.0, 5.0).name('Bloom').onChange(updateUniforms);
visualFolder.add(params, 'saturation', 0.0, 2.0).name('Saturation').onChange(updateUniforms);
visualFolder.add(params, 'grainAmount', 0.0, 0.5).name('Grain').onChange(updateUniforms);
visualFolder.add(params, 'minCircleSize', 0.0, 10.0).name('Circle Size').onChange(updateUniforms);
visualFolder.add(params, 'circleStrength', 0.0, 3.0).name('Circle Strength').onChange(updateUniforms);
visualFolder.add(params, 'distortX', 0.0, 50.0).name('Distort-X').onChange(updateUniforms);
visualFolder.add(params, 'distortY', 0.0, 50.0).name('Distort-Y').onChange(updateUniforms);
visualFolder.open();

const colorFolder = gui.addFolder('Color Tint');
colorFolder.add(params, 'colorTintR', 0.0, 1.5).name('Red').onChange(updateUniforms);
colorFolder.add(params, 'colorTintG', 0.0, 1.5).name('Green').onChange(updateUniforms);
colorFolder.add(params, 'colorTintB', 0.0, 1.5).name('Blue').onChange(updateUniforms);
colorFolder.open();

// Add refresh button
gui.add({ refresh: refreshPattern }, 'refresh').name('Refresh Pattern');

// Add toggle for zen mode (hide/show GUI and indicators)
let zenMode = false;
gui.add({ toggleZen: function() {
    zenMode = !zenMode;
    document.querySelector('.dg.ac').style.display = zenMode ? 'none' : 'block';
    document.getElementById('fpsIndicator').style.display = zenMode ? 'none' : 'block';
}}, 'toggleZen').name('Toggle Zen Mode');

// Function to update shader uniforms from GUI values
function updateUniforms() {
    gl.uniform1f(timeScaleLocation, params.timeScale);
    gl.uniform1f(patternAmpLocation, params.patternAmp);
    gl.uniform1f(patternFreqLocation, params.patternFreq);
    gl.uniform1f(bloomStrengthLocation, params.bloomStrength);
    gl.uniform1f(saturationLocation, params.saturation);
    gl.uniform1f(grainAmountLocation, params.grainAmount);
    gl.uniform3f(colorTintLocation, params.colorTintR, params.colorTintG, params.colorTintB);
    gl.uniform1f(minCircleSizeLocation, params.minCircleSize);
    gl.uniform1f(circleStrengthLocation, params.circleStrength);
    gl.uniform1f(distortXLocation, params.distortX);
    gl.uniform1f(distortYLocation, params.distortY);
}

function drawScene(){
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
}

// Animation loop
function render(timestamp) {
    if (isPlaying) {
        // Calculate adjusted time by subtracting the offset
        const adjustedTime = timestamp - timeOffset;
        time = timestamp;

        const timeInSeconds = adjustedTime * 0.0035;
        gl.uniform1f(timeLocation, timeInSeconds);
        gl.uniform2f(resolutionLocation, canvas.width, canvas.height);
        
        // FPS calculation
        frameCount++;
        
        // Update FPS every 500ms
        if (time - lastTime >= 500) {
            // Calculate FPS: frameCount / timeDiff in seconds
            fps = Math.round((frameCount * 1000) / (time - lastTime));
            fpsIndicator.textContent = `FPS: ${fps}`;
            
            // Reset for next update
            frameCount = 0;
            lastTime = time;
        }
        
        drawScene();
        
        animationID = requestAnimationFrame(render);
    }
}

// Keyboard event listener for Zen mode
document.addEventListener('keydown', function(event) {
    if (event.key === 'z' || event.key === 'Z') {
        zenMode = !zenMode;
        document.querySelector('.dg.ac').style.display = zenMode ? 'none' : 'block';
        document.getElementById('fpsIndicator').style.display = zenMode ? 'none' : 'block';
    }
});

// Start the animation loop
isPlaying = true;
refreshPattern();
updateUniforms();
handleResize();  // Set initial canvas size
animationID = requestAnimationFrame(render);