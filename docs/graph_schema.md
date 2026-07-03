# Graph Schema

## Entity Types

- `kg:Work`: scholarly paper or other OpenAlex work.
- `kg:Author`: person credited in an OpenAlex authorship.
- `kg:Institution`: author affiliation.
- `kg:Source`: journal, repository, or venue.
- `kg:Topic`: OpenAlex topic.
- `kg:Publisher`: publisher attached to a source.

## Relationships

- `kg:authoredBy`: work to author.
- `kg:cites`: work to referenced work.
- `kg:publishedIn`: work to source.
- `kg:affiliatedWith`: author to institution.
- `kg:hasTopic`: work to topic.
- `kg:publishedBy`: source to publisher.
- `kg:hasOpenAlexId`: stable OpenAlex identifier key.
- `kg:publicationYear`: publication year literal.

## IRI Pattern

```text
https://example.org/research-kg/resource/{entity_type}/{openalex_key}
```

Example:

```text
https://example.org/research-kg/resource/work/W123456789
```
