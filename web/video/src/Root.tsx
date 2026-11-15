import {Composition} from 'remotion';
import {Main, calculateMainMetadata, MainProps} from './Main';
import {testEdit} from './edits/test';

export const RemotionRoot: React.FC = () => {
  return (
    <>
      {/* One <Composition> per edit file. The final demo gets its own edit (e.g. edits/demo.ts). */}
      <Composition
        id="Test"
        component={Main}
        width={1920}
        height={1080}
        fps={30}
        durationInFrames={450}
        defaultProps={{edit: testEdit} as MainProps}
        calculateMetadata={calculateMainMetadata}
      />
      <Composition
        id="TestEric"
        component={Main}
        width={1920}
        height={1080}
        fps={30}
        durationInFrames={450}
        defaultProps={{edit: {...testEdit, voiceover: {...testEdit.voiceover!, id: 'test-eric'}}} as MainProps}
        calculateMetadata={calculateMainMetadata}
      />
    </>
  );
};
