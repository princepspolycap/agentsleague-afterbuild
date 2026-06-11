# UI Assets

This folder holds the art that ships with the public, MIT-licensed submission.
The committed baseline is **generated-art-first with a geometric fallback**:
the `/story` view draws diagrams procedurally and shows Foundry-generated
portraits when they exist, so the public repo ships with **no third-party art**
and is fully MIT-clean.

## License Rules

- Do not commit paid, restricted, or locally sourced art packs.
- Anything under `submission/ui/assets/local/` stays gitignored.
- Committed art must include a clear source, license, and attribution note when
  the license requires it.
- Prefer generated art from the configured Microsoft Foundry image deployment or
  CC0/public-domain assets.

## Foundry-Generated Art (MAI-Image-2e) - The Committed-Art Path

The repo's own way to ship game art is to **generate it on Microsoft Foundry**
with an env-configured image deployment. Generated outputs can be committed
under the repo license with responsible-AI disclosure, so forkers get both the
art and the generator.

- Config: `IMAGE_ENDPOINT`, `IMAGE_DEPLOYMENT`, `IMAGE_API_KEY` in
  `submission/.env` (see [.env.example](../../.env.example)).
- Generator: run `python submission/tools/generate_art.py` to produce the
  worker-role portraits into `generated/` (offline-safe: prints a dry-run plan
  when no deployment is configured).
- API: `POST {IMAGE_ENDPOINT}/mai/v1/images/generations` with
  `{"model": "MAI-Image-2e", "prompt": ..., "width": 1024, "height": 1024}`
  and an `api-key` header. Output is PNG.
- House style prompt prefix: "minimal flat geometric portrait, dark navy
  background, teal and gold accents, clean vector style game avatar".
- Commit generated art under `submission/ui/assets/generated/` with a note that
  it is AI-generated and which model produced it.

## Motion Backdrops (Veo) - Local-Only Enhancement

The intro lore cards can upgrade from stills to motion: if a clip named
`generated/lore/video/<scene>.mp4` exists for a scene, the intro plays the
looping clip as the full-bleed backdrop instead of the Ken Burns still. Clips
are **local-only and gitignored** because they are heavy; the committed stills
remain the baseline every fork gets.

Format: about 8 seconds, loopable, 16:9, muted, no text or logos in frame.

Drop exported MP4s into `generated/lore/video/` and reload. Disclosure: clips
are AI-generated with Google Veo 3.

## Redistributable Alternatives

To ship art inside a public MIT fork, use assets whose license permits
redistribution. Best options:

- **CC0/public domain**: cleanest. No attribution or share-alike requirements.
- **Permissive assets with attribution**: allowed only when attribution and
  license files are committed next to the assets.

If art is committed, add a `CREDITS` entry naming each pack, author, license,
and source URL next to the files.
