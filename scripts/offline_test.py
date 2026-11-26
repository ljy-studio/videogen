import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import client as c


class VideoTests(unittest.TestCase):
    def test_generate_and_resume(self):
        for model, endpoint in [('MiniMax-H3','/videos'),('FastH3-Omni','/videos'),('doubao-seedance-2-0-260128','/v1/videos')]:
            with self.subTest(model=model), tempfile.TemporaryDirectory() as directory:
                root=Path(directory)
                prompt='原文：镜头缓慢向左移动。'
                job=dict(gateway='sh',model=model,prompt=prompt,output_dir=directory)
                if model=='FastH3-Omni':
                    frame=root/'frame.png'
                    frame.write_bytes(b'\x89PNG\r\n\x1a\nfixture')
                    job['first_frame']=str(frame)
                path=root/'job.json'
                path.write_text(json.dumps(job),encoding='utf-8')
                session=MagicMock()
                session.__enter__.return_value=session
                listing=MagicMock()
                listing.json.return_value={'data':[{'id':model},{'id':'sora-2'},{'id':'text-model'}]}
                poll=MagicMock()
                poll.json.return_value={'status':'completed'}
                asset=MagicMock(status_code=200,is_redirect=False)
                asset.iter_content.return_value=[b'\x00\x00\x00\x18ftypisom'+b'\x00'*16]
                session.get.side_effect=[listing,poll,asset]
                session.post.return_value.status_code=200
                session.post.return_value.json.return_value={'status':'queued','id':'task:a/b'}
                with patch.dict(c.os.environ,GAOXIN_API_KEY='mock'),patch.object(c.requests,'Session',return_value=session),patch.object(c.time,'sleep'),patch.object(c.shutil,'which',return_value=None):
                    result=c.run(SimpleNamespace(command='generate',job=path))
                    self.assertTrue(Path(result['path']).is_file())
                    self.assertEqual(c.run(SimpleNamespace(command='resume',record=result['record']))['path'],result['path'])
                self.assertEqual(session.post.call_count,1)
                sent=session.post.call_args
                self.assertEqual(sent.args[0],c.HOSTS['sh']+endpoint)
                self.assertEqual(sent.kwargs['json']['prompt'],prompt)
                self.assertEqual(sent.kwargs['json']['seconds'],5 if endpoint.startswith('/v1') else '5')
                self.assertTrue(session.get.call_args.args[0].endswith('/task%3Aa%2Fb/content'))

    def test_byok_does_not_switch_to_environment_or_resume_with_another_key(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "record.json"
            import hashlib
            digest = hashlib.sha256(b"videogen-task-key:original").hexdigest()
            path.write_text(json.dumps(dict(profile="byok", byok_fingerprint=digest, id="task")))
            with patch.object(c.accounts, "resolve", return_value="different") as resolve, patch.object(c.requests, "Session") as session:
                with self.assertRaisesRegex(ValueError, "original_byok"):
                    c.run(SimpleNamespace(command="resume", record=path))
                resolve.assert_called_once_with("byok")
                session.assert_not_called()

    def test_unmapped_model_cannot_submit(self):
        with self.assertRaisesRegex(ValueError,'unmapped_model'):
            c.payload({'model':'sora-2','prompt':'a cat'})

if __name__=='__main__':
    unittest.main()
