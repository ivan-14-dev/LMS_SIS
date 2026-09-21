/**
 * Mock API wrapper for development and testing
 * Returns mock data only when explicitly enabled in the application configuration
 */

import { getConfig } from '@edx/frontend-platform';
import * as mockData from './mockData';

// Simulate network delay
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

/**
 * Mock API handlers mapping URL patterns to mock data
 */
const mockHandlers = {
  // Dashboard
  '/dashboard/stats': () => mockData.mockSuperieurDashboardStats,
  '/dashboard/activites': () => mockData.mockRecentActivities,
  
  // Étudiants
  '/etudiants': () => ({ results: mockData.mockEtudiants, count: mockData.mockEtudiants.length }),
  '/etudiants/': () => ({ results: mockData.mockEtudiants, count: mockData.mockEtudiants.length }),
  
  // Cours
  '/cours': () => ({ results: mockData.mockCours, count: mockData.mockCours.length }),
  '/cours/': () => ({ results: mockData.mockCours, count: mockData.mockCours.length }),
  
  // Enseignants
  '/enseignants': () => ({ results: mockData.mockEnseignants, count: mockData.mockEnseignants.length }),
  '/enseignants/': () => ({ results: mockData.mockEnseignants, count: mockData.mockEnseignants.length }),
  
  // Filières
  '/filieres': () => ({ results: mockData.mockFilieres, count: mockData.mockFilieres.length }),
  '/formations': () => ({ results: mockData.mockFilieres, count: mockData.mockFilieres.length }),
  
  // Notes
  '/notes': () => ({ results: mockData.mockNotes, count: mockData.mockNotes.length }),
  '/notes/': () => ({ results: mockData.mockNotes, count: mockData.mockNotes.length }),
  
  // Inscriptions
  '/inscriptions': () => ({ results: mockData.mockInscriptions, count: mockData.mockInscriptions.length }),
  '/inscriptions/': () => ({ results: mockData.mockInscriptions, count: mockData.mockInscriptions.length }),
  
  // Secondaire Dashboard
  '/secondaire/dashboard/stats': () => mockData.mockSecondaireDashboardStats,
  
  // Élèves
  '/eleves': () => ({ results: mockData.mockEleves, count: mockData.mockEleves.length }),
  '/eleves/': () => ({ results: mockData.mockEleves, count: mockData.mockEleves.length }),
  
  // Classes
  '/classes': () => ({ results: mockData.mockClasses, count: mockData.mockClasses.length }),
  '/classes/': () => ({ results: mockData.mockClasses, count: mockData.mockClasses.length }),
  
  // Présences
  '/presences': () => ({ results: mockData.mockPresences, count: mockData.mockPresences.length }),
  '/presences/': () => ({ results: mockData.mockPresences, count: mockData.mockPresences.length }),
  
  // Bulletins
  '/bulletins': () => ({ results: mockData.mockBulletins, count: mockData.mockBulletins.length }),
  '/bulletins/': () => ({ results: mockData.mockBulletins, count: mockData.mockBulletins.length }),
  
  // Évaluations
  '/evaluations': () => ({ results: mockData.mockEvaluations, count: mockData.mockEvaluations.length }),
  '/evaluations/': () => ({ results: mockData.mockEvaluations, count: mockData.mockEvaluations.length }),
  
  // Admin - Établissement
  '/etablissement': () => mockData.mockEtablissement,
  '/admin/etablissement': () => mockData.mockEtablissement,
  
  // Admin - Utilisateurs
  '/utilisateurs': () => ({ results: mockData.mockUtilisateurs, count: mockData.mockUtilisateurs.length }),
  '/admin/utilisateurs': () => ({ results: mockData.mockUtilisateurs, count: mockData.mockUtilisateurs.length }),
  
  // Admin - Structure
  '/structure': () => mockData.mockStructure,
  '/admin/structure': () => mockData.mockStructure,
  
};

/**
 * Find a matching mock handler for a URL
 */
const findMockHandler = (url) => {
  // Try exact match first
  if (mockHandlers[url]) {
    return mockHandlers[url];
  }
  
  // Try partial match
  for (const pattern of Object.keys(mockHandlers)) {
    if (url.includes(pattern)) {
      return mockHandlers[pattern];
    }
  }
  
  // Handle detail endpoints (e.g., /etudiants/1/)
  const detailMatch = url.match(/\/(\w+)\/(\d+)\/?$/);
  if (detailMatch) {
    const [, resource, id] = detailMatch;
    const listHandler = mockHandlers[`/${resource}`] || mockHandlers[`/${resource}/`];
    if (listHandler) {
      const data = listHandler();
      const items = data.results || data;
      if (Array.isArray(items)) {
        const item = items.find(i => i.id === parseInt(id, 10));
        return () => item || items[0];
      }
    }
  }
  
  return null;
};

/**
 * Mock fetch function that returns mock data
 */
export const mockFetch = async (url) => {
  await delay(300 + Math.random() * 500); // Simulate network delay
  
  const handler = findMockHandler(url);
  if (handler) {
    console.log(`[Mock API] GET ${url}`);
    return handler();
  }
  
  console.warn(`[Mock API] No handler found for: ${url}`);
  return { results: [], count: 0 };
};

/**
 * Mock post function
 */
export const mockPost = async (url, data) => {
  await delay(300 + Math.random() * 300);
  console.log(`[Mock API] POST ${url}`, data);
  return { ...data, id: Date.now(), created_at: new Date().toISOString() };
};

/**
 * Mock put function
 */
export const mockPut = async (url, data) => {
  await delay(200 + Math.random() * 200);
  console.log(`[Mock API] PUT ${url}`, data);
  return { ...data, updated_at: new Date().toISOString() };
};

/**
 * Mock delete function
 */
export const mockDelete = async (url) => {
  await delay(200 + Math.random() * 200);
  console.log(`[Mock API] DELETE ${url}`);
  return { success: true };
};

/**
 * Check if mock mode is enabled
 */
export const isMockMode = () => {
  const { USE_MOCK_API } = getConfig();
  return USE_MOCK_API === true || USE_MOCK_API === 'true';
};
