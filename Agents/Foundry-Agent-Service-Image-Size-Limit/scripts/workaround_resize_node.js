/**
 * Resize image before sending to Foundry Agent Service
 * Keeps request body under the ~64KB gateway limit
 * 
 * Usage: npm install sharp   (one-time)
 * Then replace your base64 encoding line with resizeAndEncode()
 */
const sharp = require('sharp');
const fs = require('fs');

/**
 * Resize image to fit within Agent Service body limit.
 * GPT-4o-mini detail:low uses 512x512, detail:auto uses up to 2048x2048.
 * Resizing before sending does NOT reduce model understanding quality.
 * 
 * @param {string|Buffer} input - File path or Buffer
 * @param {object} opts
 * @param {number} opts.maxBodyKB - Max request body in KB (default: 60, safe margin below 64KB limit)
 * @param {number} opts.maxWidth - Max pixel width (default: 1024)
 * @param {number} opts.maxHeight - Max pixel height (default: 1024)
 * @returns {Promise<{base64: string, originalKB: number, resizedKB: number, wasResized: boolean}>}
 */
async function resizeAndEncode(input, opts = {}) {
    const { maxBodyKB = 60, maxWidth = 1024, maxHeight = 1024 } = opts;
    
    const buf = Buffer.isBuffer(input) ? input : fs.readFileSync(input);
    const originalKB = buf.length / 1024;
    
    // JSON overhead: ~220 bytes for the Responses API payload wrapper
    const maxImageB64KB = maxBodyKB - 1;  // leave 1KB for JSON overhead
    const maxImageBytes = Math.floor(maxImageB64KB * 1024 * 3 / 4);  // b64 expands 4/3x
    
    if (buf.length <= maxImageBytes) {
        // Small enough, no resize needed
        return {
            base64: buf.toString('base64'),
            originalKB: Math.round(originalKB),
            resizedKB: Math.round(originalKB),
            wasResized: false
        };
    }
    
    // Resize: fit within maxWidth x maxHeight, then compress JPEG
    let quality = 80;
    let resized;
    
    for (let attempt = 0; attempt < 5; attempt++) {
        resized = await sharp(buf)
            .resize(maxWidth, maxHeight, { fit: 'inside', withoutEnlargement: true })
            .jpeg({ quality })
            .toBuffer();
        
        if (resized.length <= maxImageBytes) break;
        quality -= 10;  // reduce quality if still too large
        maxWidth = Math.floor(maxWidth * 0.8);
        maxHeight = Math.floor(maxHeight * 0.8);
    }
    
    return {
        base64: resized.toString('base64'),
        originalKB: Math.round(originalKB),
        resizedKB: Math.round(resized.length / 1024),
        wasResized: true
    };
}

// --- Example: drop-in replacement for Lenovo's flow ---
async function sendImageToFoundry(imagePath, token, endpoint) {
    const { base64, originalKB, resizedKB, wasResized } = await resizeAndEncode(imagePath);
    
    if (wasResized) {
        console.log(`Image resized: ${originalKB}KB -> ${resizedKB}KB`);
    }
    
    const payload = {
        model: "gpt-4o-mini",
        instructions: "You are an AI assistant that helps people find information.",
        input: [{
            role: "user",
            content: [
                { type: "input_text", text: "Describe this image briefly." },
                { type: "input_image", image_url: `data:image/jpeg;base64,${base64}`, detail: "auto" }
            ]
        }],
        max_output_tokens: 500
    };
    
    const resp = await fetch(endpoint, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(payload)
    });
    
    return resp.json();
}

module.exports = { resizeAndEncode, sendImageToFoundry };
