# Session 22 decisions

## D37: Third source card swapped to one with a real lead image
- The arXiv paper has no lead image, so its card showed a short checker band and broke the row. It is replaced by Lyft Engineering, "Real-Time Spatial Temporal Forecasting @ Lyft" (Josh Xi and Rakesh Kumar, 5 May 2025), read in full metadata: its subtitle is "Reliability and Simplicity: A Look at Classical Time-Series Models for Real-Time Forecasting", and its intro lists real-time rider pricing, driver incentives, budget allocation and planning as uses of forecasts. The card's one-line reason stays within that.
- Image is the page's own og:image, linked not copied, credited "Image: Lyft Engineering". The post is all rights reserved, which is another reason not to copy the file.
- All three cards now measure the same (476 px high, image 150 px) in the preview.
- The arXiv paper is dropped from the page. It is still a fair citation for the README.

## Open item: typefaces
- Screenshots from the live run show system fallbacks (an Arial-Narrow-like sans and a Georgia-like serif) instead of the bundled fonts, so static font serving is probably not reaching his browser. Plan: embed the chosen fonts directly in the page CSS so loading does not depend on a server setting, then choose between three specimen pairings.
