const hospitalSvgRaw = `<svg xmlns="http://www.w3.org/2000/svg"
     width="36" height="40"
     viewBox="0 0 32 40"
     aria-hidden="true">

  <!-- marker body with black outline -->
  <path d="M16 2
           C9 2 4 7 4 14
           c0 9 12 20 12 20
           s12-11 12-20
           C28 7 23 2 16 2Z"
        fill="#ff4d4d" stroke="#111111" stroke-width="2"/>

  <!-- white circle with black outline -->
  <circle cx="16" cy="14" r="7" fill="#ffffff"/>

  <!-- red cross (centered at 16,14) -->
  <path d="M14 9h4v4h4v4h-4v4h-4v-4h-4v-4h4z"
        fill="#ff4d4d"/>

  <!-- ground ring (red) -->
  <ellipse cx="16" cy="36" rx="9" ry="2.5"
           fill="none" stroke="#ff4d4d" stroke-width="2"/>
</svg>

`;
export const hospitalSvg = "data:image/svg+xml;utf8," + encodeURIComponent(hospitalSvgRaw);
