# Session 21 decisions

## D36: Lead images on the source cards, linked not copied
- Each card can show the article's own lead image, using the address the publisher puts in its og:image tag (read from the live pages: Uber blog, NY1). The image is not downloaded into the repository. The visitor's browser loads it from the publisher, as a link preview does, with a credit line under it ("Image: Uber", "Image: AP file photo, via NY1") and the whole card linking to the original.
- If an image is missing or fails to load, the card shows a taxi checker band instead, so nothing looks broken. The arXiv paper has no image, so it always shows the band.
- Why not copy the files: the NY1 photo is an AP file photo, so the rights sit with AP and NY1, and a copy in a public repo is a copy we would be distributing.
- Trade-offs: the publisher could change or remove the image, and loading it tells the publisher's server that someone opened the page. The image address cannot be checked from the build sandbox, so loading on the live app is unverified.
- Safety: image addresses must be https and are rejected if they contain quotes, brackets, spaces or semicolons, because they sit inside a CSS url(). A test covers a hostile address.
