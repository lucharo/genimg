# Changelog

## 0.1.0 (2026-09-14)


### Features

* add GenIMG infographic skill ([#29](https://github.com/lucharo/genimg/issues/29)) ([55c6dbb](https://github.com/lucharo/genimg/commit/55c6dbb006dcacc0e4b2934c323234d5a0349750))
* add GPT Image 2.5 and subscription image generation ([#33](https://github.com/lucharo/genimg/issues/33)) ([8fda355](https://github.com/lucharo/genimg/commit/8fda355862abfef465049d78890e96dace2a5fa5))
* add image-to-app workflow skill ([3cf34db](https://github.com/lucharo/genimg/commit/3cf34db2da90f58ef964e1f8f6caad28394f712e))
* add interactive generation history browser ([ddaec60](https://github.com/lucharo/genimg/commit/ddaec6057d99564991705ee3f1ea668dae90913a))
* **auth:** surface preflight readiness in `genimg auth` ([a2d2102](https://github.com/lucharo/genimg/commit/a2d2102a1ac85531780d4dda9d1dbf9c3d6e7d1e))
* automate infographic design choices ([#30](https://github.com/lucharo/genimg/issues/30)) ([94bc9c4](https://github.com/lucharo/genimg/commit/94bc9c45ccf77f311cbe8e00183112876a69ea6d))
* **cli:** codex-rescue ergonomic pass ([85d691e](https://github.com/lucharo/genimg/commit/85d691e0894f791c6f9b034a8d8c501f02bf4643))
* **draw:** add `genimg draw` studio (web canvas → genimg) ([#16](https://github.com/lucharo/genimg/issues/16)) ([e9c7a58](https://github.com/lucharo/genimg/commit/e9c7a5817dd3579bbf2f43cd186ecea5e5b9052d))
* **draw:** improve Studio model and prompt controls ([#26](https://github.com/lucharo/genimg/issues/26)) ([22fb4a1](https://github.com/lucharo/genimg/commit/22fb4a1ef83c57af6c16a05d400c39ff7deb01d2))
* embed metadata into PNGs; rework grid metadata layout ([60c12c6](https://github.com/lucharo/genimg/commit/60c12c69729f19c612b0a8db25fccac69f509d0c)), closes [#8](https://github.com/lucharo/genimg/issues/8)
* **grid:** metadata panel + carousel view in HTML grid ([ea8adc2](https://github.com/lucharo/genimg/commit/ea8adc2c702f30d9d244e9daad07062ce970d2ae))
* **grid:** persist view, prompt, and carousel index in URL params ([6a13a55](https://github.com/lucharo/genimg/commit/6a13a55593839b6b0e38a17e6d3f734c43b7b029))
* initial release of genimg multi-provider image CLI ([00a02c2](https://github.com/lucharo/genimg/commit/00a02c2ee2277fd0d2e10f722b30e23deddc8107))
* **setup:** rewrite wizard — detect, fetch, validate, save ([396e1d1](https://github.com/lucharo/genimg/commit/396e1d17ca4817233a81ba70d39ff34763d199b4))
* sharpen history previews and add yank shortcuts ([e63a1d7](https://github.com/lucharo/genimg/commit/e63a1d75308bc83403a9a677399fa13e623a35ab))


### Bug Fixes

* address roborev [#1153](https://github.com/lucharo/genimg/issues/1153) findings (3 correctness bugs) ([1ff06d7](https://github.com/lucharo/genimg/commit/1ff06d70e3817fe8b8ede1fda2af5dce780a1476))
* address roborev [#1154](https://github.com/lucharo/genimg/issues/1154) findings (OpenAI size correctness) ([df82f78](https://github.com/lucharo/genimg/commit/df82f78f8c9eb8dd7c8f8614db429c6c5cd01449))
* address roborev [#1155](https://github.com/lucharo/genimg/issues/1155) (implicit-1K aspect validation gap) ([72b7354](https://github.com/lucharo/genimg/commit/72b7354d7ab3553081a009520e5de9da5df79190))
* address roborev [#2871](https://github.com/lucharo/genimg/issues/2871) findings ([87941fc](https://github.com/lucharo/genimg/commit/87941fcc3a6b9ed17f80a6b9df8a8d1d86b572a7))
* address roborev [#2872](https://github.com/lucharo/genimg/issues/2872) — auth_info endpoint mislabel for native config ([c48a59a](https://github.com/lucharo/genimg/commit/c48a59a4a3f31d5203021b7f4f55997f64adeca9))
* address roborev [#2874](https://github.com/lucharo/genimg/issues/2874) findings ([967aa22](https://github.com/lucharo/genimg/commit/967aa225d60a55c29c2cd1e58ed3590c4b1fff65))
* address roborev [#2875](https://github.com/lucharo/genimg/issues/2875) — drop misleading HTML cost footer too ([d3af953](https://github.com/lucharo/genimg/commit/d3af9530a9f98aa117530f4e9c1613e6b28d52ad))
* **draw:** restore generation lifecycle ([82ea06c](https://github.com/lucharo/genimg/commit/82ea06c4f38093d158a7f64743fc7d473a656a38))
* **genimg:** declare click dep and cap typer&lt;0.26 for default-command routing ([#11](https://github.com/lucharo/genimg/issues/11)) ([fc9d122](https://github.com/lucharo/genimg/commit/fc9d12288eb92128b63c9e220ec87f33cf2b14ff))
* **grid:** HTML-escape label/src/filename in grid cards ([8259c88](https://github.com/lucharo/genimg/commit/8259c882d9290fb0982da0576e865275e561a478))
* **metadata:** preserve existing PNG text chunks when embedding ([71c78c3](https://github.com/lucharo/genimg/commit/71c78c3a8cd12289a5b68c6ed9ac3ba0a425e13f))
* prepare v0.1.0 release core ([#31](https://github.com/lucharo/genimg/issues/31)) ([9c54b35](https://github.com/lucharo/genimg/commit/9c54b357262ed6559d0bf5d195562ceba4ec85be))
* preserve metadata when grid render fails ([54dea20](https://github.com/lucharo/genimg/commit/54dea208c29d53a2d02468849974e524e9e6839e))
* render history help key labels literally ([922bc37](https://github.com/lucharo/genimg/commit/922bc37ce23d4ef23d74793ab23204bc2b6ab11d))
* **setup:** drop Rich markup from questionary choice labels ([4899162](https://github.com/lucharo/genimg/commit/489916279bc976a17d234b9618abada011d4a957))
* **setup:** show concrete env var + masked value per choice ([ee56e12](https://github.com/lucharo/genimg/commit/ee56e1243e6f231dfcfc6ebe79d760647af2e6f1))
* **skill:** strip YAML frontmatter before passing infographic prompt to genimg ([0de6b01](https://github.com/lucharo/genimg/commit/0de6b01c4c854977837e74df3467c9b9175f72c9))


### Documentation

* clarify how to get the most output variety ([#20](https://github.com/lucharo/genimg/issues/20)) ([1b9266b](https://github.com/lucharo/genimg/commit/1b9266bcb61ad9137393f5bcc9727b53f816daff))
* **cli:** drop stale built-in-default references from help strings ([#19](https://github.com/lucharo/genimg/issues/19)) ([8e98ed2](https://github.com/lucharo/genimg/commit/8e98ed2227790d86f3d61ae545f690d2fa074330))
* distinguish provider and CLI timing ([2c01305](https://github.com/lucharo/genimg/commit/2c01305cbe7741fbbabc6dba70381162ce41f821))
* explain Draw Studio and iPad workflow ([9ef385e](https://github.com/lucharo/genimg/commit/9ef385e84ef626492058d22b3e54a85f9ba2dc63))
* fix Imagen-misleading wording in cheat-sheet ([#21](https://github.com/lucharo/genimg/issues/21)) ([84e5cee](https://github.com/lucharo/genimg/commit/84e5cee56092a4a6b1b7ed0506904fabfdb85dd6))
* **metadata:** note Pillow re-save drops C2PA chunks; use as_uri for grid open ([29e7806](https://github.com/lucharo/genimg/commit/29e780660d8b2edc14b6ebf1a2d1b2fe095cb7e3))
* refresh README for v0.2.0 surface ([4c45daf](https://github.com/lucharo/genimg/commit/4c45dafd81d0d70f23db52927a9891a442217920))
* **skill:** -q on gdm models is rejected by the CLI, not silently ignored ([e0579e6](https://github.com/lucharo/genimg/commit/e0579e62a0ca4ca8277741425e1ded252b83c33d))
* **skill:** add a generation flag table so agents stop parsing --help ([#35](https://github.com/lucharo/genimg/issues/35)) ([ed7c10a](https://github.com/lucharo/genimg/commit/ed7c10a35158bb3266652a7967897251a119d9c0))
* **skill:** add diagram/infographic guidance; gemini &gt; gpt-image-2 for structure ([6044280](https://github.com/lucharo/genimg/commit/6044280a7918474e3556b7f06175c3bab9912cfa))
* **skill:** add reviewing & sharing-results section ([ca7e9d5](https://github.com/lucharo/genimg/commit/ca7e9d512a034900ed20c3287b39f32d47712a8a))
* **skill:** background-open option + grid metadata note ([528ac4b](https://github.com/lucharo/genimg/commit/528ac4b2340f1b75d37b9b638fa17987ed2886f0))
* **skill:** correct default model — gdm:nb2, not oai:gi2 ([7130dae](https://github.com/lucharo/genimg/commit/7130dae28d2ac83e4834b3c6f50e55a92709e0fa))
* **skill:** matting solidify, sprite-sheet slicing, style-lock patterns ([72e2192](https://github.com/lucharo/genimg/commit/72e2192f549c1d4df9d625de7d0c9c2be571eee5))
* strengthen image-to-app evidence ladder ([da061e1](https://github.com/lucharo/genimg/commit/da061e1bccc01d8d0d8b281e251066c69b3892c9))
