# Reference images

Copy each reference file the user supplied into the output directory as `refs/NN-ref-<slug>.<ext>`, so the prompt stays reproducible, and check each copy exists before generating.

Assign one usage mode per reference. When the user has not named one, infer it from their stated intent.

| Usage | Effect |
| --- | --- |
| `direct` | Pass the preserved file positionally to GenIMG for composition, subject or close visual guidance |
| `style` | Describe its line treatment, texture, lighting and mood in the prompt; the file stays off the command line |
| `palette` | Extract representative hex colours into the prompt; the file stays off the command line |

GenIMG takes references as positional file arguments after the prompt; it has no `--ref` option. Only `direct` references appear there.

Record the provenance and the reasoning for each mode in the `prompts/infographic.md` frontmatter:

```yaml
references:
  - ref_id: 01
    filename: refs/01-ref-brand.png
    usage: direct
```
