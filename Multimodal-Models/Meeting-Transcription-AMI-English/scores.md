| Model | WER (all clips) | Errors / ref words | Sub / Del / Ins | EN2002a_0106p13-0179p93 | ES2004a_0850p73-0912p60 | IS1009a_0685p59-0758p09 | TS3003a_1246p83-1320p78 |
|---|---|---|---|---|---|---|---|
| fast-en | 22.4% | 208 / 930 | 41 / 163 / 4 | 21.1% | 24.2% | 19.1% | 25.0% |
| gpt-batch | 20.5% | 191 / 930 | 40 / 142 / 9 | 21.5% | 18.6% | 16.7% | 25.0% |
| gpt-live | 21.3% | 198 / 930 | 49 / 144 / 5 | 20.8% | 19.5% | 18.1% | 26.8% |
| mai-batch | 15.8% | 147 / 930 | 36 / 96 / 15 | 15.0% | 14.3% | 13.0% | 21.0% |
| mai-stream | 17.7% | 165 / 930 | 48 / 103 / 14 | 15.8% | 19.9% | 14.4% | 21.0% |
| speech-rt | 24.8% | 231 / 930 | 56 / 170 / 5 | 23.8% | 24.2% | 17.2% | 33.9% |

| Model | First text, any (s, median) | First finalized text (s, median) | Final text after audio end (s, median) | Whole-file request (s, median) |
|---|---|---|---|---|
| fast-en | - | - | - | 7.777 |
| gpt-batch | - | - | - | 7.707 |
| gpt-live | 2.795 | 2.795 | 1.255 | - |
| mai-batch | - | - | - | 6.707 |
| mai-stream | 0.789 | 2.943 | 0.442 | - |
| speech-rt | 3.744 | 11.125 | 0.583 | - |
