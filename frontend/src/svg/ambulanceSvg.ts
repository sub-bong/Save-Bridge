const ambulanceSvgRaw = `
<svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 96 64">
  <ellipse cx="48" cy="58" rx="30" ry="3" fill="#e5e5e5"/>
  <rect x="6" y="10" width="54" height="32" rx="5" fill="#f1f1f1" stroke="#111" stroke-width="2"/>
  <path d="M60 18h14c1.4 0 2.6 1 3 2.4L79 42H60Z" fill="#bff0f2" stroke="#111" stroke-width="2"/>
  <rect x="58" y="15" width="14" height="3" fill="#f1f1f1" stroke="#111" stroke-width="1.5"/>
  <ellipse cx="65" cy="14" rx="4" ry="5" fill="#ff5757" stroke="#111" stroke-width="1.5"/>
  <path d="M6 34h70a9 9 0 0 1 9 9v3H6Z" fill="#ff5757" stroke="#111" stroke-width="2"/>
  <rect x="6" y="43" width="82" height="7" fill="#f7f7f7" stroke="#111" stroke-width="1.5"/>
  <rect x="62" y="34" width="7" height="4" rx="2" fill="#ffffff" stroke="#111" stroke-width="1.2"/>
  <g transform="translate(26,18)" fill="#ff5757" stroke="#111" stroke-width="1.2">
    <rect x="-3" y="0" width="6" height="14" rx="2"/>
    <rect x="-9" y="5" width="18" height="5" rx="2"/>
  </g>
  <circle cx="22" cy="52" r="8" fill="#58595b" stroke="#111" stroke-width="2.5"/>
  <circle cx="22" cy="52" r="3" fill="#efefef" stroke="#111" stroke-width="1.2"/>
  <circle cx="72" cy="52" r="8" fill="#58595b" stroke="#111" stroke-width="2.5"/>
  <circle cx="72" cy="52" r="3" fill="#efefef" stroke="#111" stroke-width="1.2"/>
</svg>
`;
export const ambulanceSvg = "data:image/svg+xml;utf8," + encodeURIComponent(ambulanceSvgRaw);
