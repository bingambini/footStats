import { createClient } from '@supabase/supabase-js';

// ეს ცვლადები GitHub Actions-იდან ან გარემოდან წამოვა
const supabaseUrl = process.env.SUPABASE_URL || 'YOUR_SUPABASE_URL';
const supabaseAnonKey = process.env.SUPABASE_ANON_KEY || 'YOUR_SUPABASE_ANON_KEY';

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

console.log("⚽ Football Analytics Engine Initialized Successfully!");