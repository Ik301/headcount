import {Config} from '@remotion/cli/config';

// H.264 at high quality; JPEG intermediate frames are fine for screen content at this quality.
Config.setVideoImageFormat('jpeg');
Config.setJpegQuality(92);
Config.setCodec('h264');
Config.setCrf(16);
Config.setPixelFormat('yuv420p');
Config.setConcurrency(3); // 4 vCPUs on the VM; leave one for the encoder
Config.setOverwriteOutput(true);
