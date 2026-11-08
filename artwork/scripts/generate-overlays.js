const fs = require('fs');
const path = require('path');
const sharp = require('sharp');

const overlaysDir = path.join(__dirname, '../public/overlays');

if (!fs.existsSync(overlaysDir)) {
  fs.mkdirSync(overlaysDir, { recursive: true });
}

// 1. 4K UHD Banner SVG
const svg4k = `
<svg width="1000" height="150" viewBox="0 0 1000 150" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="gold-grad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#FFE259"/>
      <stop offset="100%" stop-color="#FFA751"/>
    </linearGradient>
    <linearGradient id="bg-grad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#000000" stop-opacity="0.9"/>
      <stop offset="30%" stop-color="#141414" stop-opacity="0.95"/>
      <stop offset="70%" stop-color="#141414" stop-opacity="0.95"/>
      <stop offset="100%" stop-color="#000000" stop-opacity="0.9"/>
    </linearGradient>
  </defs>
  <!-- Background bar -->
  <rect width="1000" height="110" fill="url(#bg-grad)"/>
  <rect y="110" width="1000" height="5" fill="url(#gold-grad)"/>
  
  <!-- Content Shadow (for separation) -->
  <text x="500" y="79" font-family="system-ui, -apple-system, sans-serif" font-weight="900" font-size="52" fill="#000000" fill-opacity="0.5" text-anchor="middle" letter-spacing="4">4K ULTRA HD</text>
  
  <!-- Main Gold Text -->
  <text x="500" y="76" font-family="system-ui, -apple-system, sans-serif" font-weight="900" font-size="52" fill="url(#gold-grad)" text-anchor="middle" letter-spacing="4">4K ULTRA HD</text>
</svg>
`;

// 2. Dolby Vision Banner SVG
const svgDolby = `
<svg width="1000" height="150" viewBox="0 0 1000 150" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="dolby-grad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#E29063"/>
      <stop offset="50%" stop-color="#E585BB"/>
      <stop offset="100%" stop-color="#8E54E9"/>
    </linearGradient>
    <linearGradient id="bg-grad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#000000" stop-opacity="0.9"/>
      <stop offset="30%" stop-color="#141414" stop-opacity="0.95"/>
      <stop offset="70%" stop-color="#141414" stop-opacity="0.95"/>
      <stop offset="100%" stop-color="#000000" stop-opacity="0.9"/>
    </linearGradient>
  </defs>
  <!-- Background bar -->
  <rect width="1000" height="110" fill="url(#bg-grad)"/>
  <rect y="110" width="1000" height="5" fill="url(#dolby-grad)"/>
  
  <!-- Dolby Double D Logo and Text grouped and centered -->
  <g transform="translate(325, 33)">
    <!-- Shadow for Dolby Logo -->
    <path d="M 15,5 h 15 v 34 h -15 a 17,17 0 0,1 0,-34 Z" fill="#000000" fill-opacity="0.5" transform="rotate(180 22.5 24) translate(-2, 2)" />
    <path d="M 30,5 h 15 v 34 h -15 a 17,17 0 0,1 0,-34 Z" fill="#000000" fill-opacity="0.5" transform="translate(2, 2)" />
    
    <!-- Dolby Logo -->
    <path d="M 15,5 h 15 v 34 h -15 a 17,17 0 0,1 0,-34 Z" fill="#ffffff" transform="rotate(180 22.5 24)" />
    <path d="M 30,5 h 15 v 34 h -15 a 17,17 0 0,1 0,-34 Z" fill="#ffffff" />
    
    <!-- Text Shadow -->
    <text x="65" y="38" font-family="system-ui, -apple-system, sans-serif" font-weight="800" font-size="38" fill="#000000" fill-opacity="0.5" letter-spacing="6">DOLBY VISION</text>
    <!-- Text -->
    <text x="63" y="36" font-family="system-ui, -apple-system, sans-serif" font-weight="800" font-size="38" fill="#ffffff" letter-spacing="6">DOLBY VISION</text>
  </g>
</svg>
`;

// 3. HDR10+ Banner SVG
const svgHDR = `
<svg width="1000" height="150" viewBox="0 0 1000 150" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="hdr-grad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#00C6FF"/>
      <stop offset="100%" stop-color="#0072FF"/>
    </linearGradient>
    <linearGradient id="bg-grad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#000000" stop-opacity="0.9"/>
      <stop offset="30%" stop-color="#141414" stop-opacity="0.95"/>
      <stop offset="70%" stop-color="#141414" stop-opacity="0.95"/>
      <stop offset="100%" stop-color="#000000" stop-opacity="0.9"/>
    </linearGradient>
  </defs>
  <!-- Background bar -->
  <rect width="1000" height="110" fill="url(#bg-grad)"/>
  <rect y="110" width="1000" height="5" fill="url(#hdr-grad)"/>
  
  <!-- HDR10+ elements centered -->
  <g transform="translate(390, 28)">
    <!-- HDR text shadow -->
    <text x="10" y="44" font-family="system-ui, -apple-system, sans-serif" font-weight="900" font-size="44" fill="#000000" fill-opacity="0.5" text-anchor="end">HDR</text>
    <!-- HDR text -->
    <text x="8" y="42" font-family="system-ui, -apple-system, sans-serif" font-weight="900" font-size="44" fill="#ffffff" text-anchor="end">HDR</text>
    
    <!-- 10+ pill shadow -->
    <rect x="24" y="8" width="114" height="42" rx="21" fill="#000000" fill-opacity="0.5" />
    <!-- 10+ pill background -->
    <rect x="22" y="6" width="114" height="42" rx="21" fill="url(#hdr-grad)" />
    
    <!-- 10+ text shadow -->
    <text x="79" y="38" font-family="system-ui, -apple-system, sans-serif" font-weight="900" font-size="28" fill="#000000" fill-opacity="0.3" text-anchor="middle">10+</text>
    <!-- 10+ text -->
    <text x="79" y="36" font-family="system-ui, -apple-system, sans-serif" font-weight="900" font-size="28" fill="#ffffff" text-anchor="middle">10+</text>
  </g>
</svg>
`;

async function main() {
  try {
    console.log('Generating transparent PNG overlays using sharp...');
    
    await sharp(Buffer.from(svg4k))
      .png()
      .toFile(path.join(overlaysDir, '4k_uhd.png'));
    console.log('✓ Generated overlays/4k_uhd.png');
    
    await sharp(Buffer.from(svgDolby))
      .png()
      .toFile(path.join(overlaysDir, 'dolby_vision.png'));
    console.log('✓ Generated overlays/dolby_vision.png');
    
    await sharp(Buffer.from(svgHDR))
      .png()
      .toFile(path.join(overlaysDir, 'hdr10.png'));
    console.log('✓ Generated overlays/hdr10.png');
    
    console.log('All overlay banners generated successfully!');
  } catch (err) {
    console.error('Error generating overlays:', err);
    process.exit(1);
  }
}

main();
