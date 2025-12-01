import React, { useRef } from "react";

interface STTInputProps {
  sttText: string;
  setSttText: (text: string) => void;
  isRecording: boolean;
  recordingError: string;
  voiceMode: boolean;
  setVoiceMode: (mode: boolean) => void;
  audioFile: File | null;
  setAudioFile: (file: File | null) => void;
  onStartRecording: () => void;
  onStopRecording: () => void;
  onAudioFileChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onUploadAudio: () => void;
}

export const STTInput: React.FC<STTInputProps> = ({
  sttText,
  setSttText,
  isRecording,
  recordingError,
  voiceMode,
  setVoiceMode,
  audioFile,
  setAudioFile,
  onStartRecording,
  onStopRecording,
  onAudioFileChange,
  onUploadAudio,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);

  return (
    <section className="bg-white rounded-lg shadow-md p-6 border border-gray-200">
      <h2 className="text-lg font-bold mb-4 text-gray-900 border-b-2 border-gray-300 pb-2">
        증상 정보 입력
      </h2>
      <p className="text-sm text-gray-600 mb-4">
        구급대원이 확인한 환자 증상을 음성 또는 텍스트로 입력하세요.
      </p>
      <div className="flex gap-3 mb-3">
        {!isRecording ? (
          <button
            className="px-6 py-3 rounded-lg bg-slate-700 text-white text-base font-semibold hover:bg-slate-800 transition shadow-md disabled:opacity-50 min-h-[48px]"
            onClick={onStartRecording}
            disabled={!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia}
          >
            음성 녹음 시작
          </button>
        ) : (
          <button
            className="px-6 py-3 rounded-lg bg-red-600 text-white text-base font-semibold hover:bg-red-700 transition shadow-md min-h-[48px]"
            onClick={onStopRecording}
          >
            녹음 중지
          </button>
        )}
        {sttText && (
          <button
            className="px-6 py-3 rounded-lg bg-gray-200 text-gray-700 text-base font-semibold hover:bg-gray-300 transition shadow-md min-h-[48px]"
            onClick={() => {
              setSttText("");
              setVoiceMode(false);
            }}
          >
            초기화
          </button>
        )}
      </div>
      {recordingError && (
        <div className="mb-3 p-4 bg-red-50 border-2 border-red-300 rounded-lg">
          <p className="text-sm text-red-800 font-semibold">{recordingError}</p>
        </div>
      )}
      {isRecording && (
        <div className="mb-3 p-4 bg-blue-50 border-2 border-blue-300 rounded-lg">
          <p className="text-sm text-blue-800 flex items-center gap-2 font-semibold">
            <span className="w-3 h-3 bg-red-600 rounded-full animate-pulse"></span>
            <span>녹음 중입니다. 중지 버튼을 눌러 녹음을 완료하세요.</span>
          </p>
        </div>
      )}
      {voiceMode && !isRecording && (
        <div className="mb-3 p-4 bg-yellow-50 border-2 border-yellow-300 rounded-lg">
          <p className="text-sm text-yellow-900 mb-3 font-semibold">
            음성 파일 업로드: 마이크 녹음이 작동하지 않으면 미리 녹음한 음성 파일(.wav, .mp3, .m4a)을 업로드하세요.
          </p>
          <div className="flex gap-3">
            <input
              ref={fileInputRef}
              type="file"
              accept="audio/*"
              onChange={onAudioFileChange}
              className="text-sm"
            />
            {audioFile && (
              <button
                className="px-4 py-2 rounded-lg bg-slate-700 text-white text-sm font-semibold hover:bg-slate-800 transition shadow-md"
                onClick={onUploadAudio}
              >
                음성 파일 분석
              </button>
            )}
          </div>
        </div>
      )}
      <textarea
        className="w-full min-h-[120px] rounded-lg border-2 border-slate-300 px-4 py-3 text-base focus:outline-none focus:ring-2 focus:ring-slate-600 focus:border-slate-600"
        placeholder="구급대원이 확인한 환자 증상 요약을 입력하세요."
        value={sttText}
        onChange={(e) => setSttText(e.target.value)}
      />
      {sttText && (
        <div className="mt-3 p-4 bg-slate-50 border-2 border-slate-300 rounded-lg">
          <p className="text-sm text-slate-900 font-semibold mb-1">음성 인식 결과:</p>
          <p className="text-sm text-slate-800">{sttText}</p>
        </div>
      )}
    </section>
  );
};

