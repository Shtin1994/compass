// --- START OF FILE frontend/src/types/index.ts ---

// Этот файл служит центральной точкой для всех типов в приложении.
// Он ре-экспортирует всё из других файлов с типами в этой директории,
// что позволяет нам делать чистые импорты из одного места, например:
// import { Channel, PostDetailsData } from '@/types';

export * from './analytics';
export * from './channel';
export * from './data';
export * from './insight';
export * from './comment'; // Добавляем экспорт из нашего нового файла

// --- END OF FILE frontend/src/types/index.ts ---